import logging
import uuid
from typing import Callable, List
from types import SimpleNamespace
from functools import wraps
from inspect import signature

from cryptography.fernet import InvalidToken
from starlette.concurrency import run_in_threadpool

from src.core.crypto import decrypt_token
from src.core.index_sync_service import IndexSyncService
from src.core.instrument_service import InstrumentService
from src.models.action import Action
from src.models.balancer_params import BalancerParams
from src.models.error import Error as DomainError
from src.models.index_composition import CompositionSnapshot
from src.models.instrument_directory import InstrumentDirectory
from src.models.api_user import (
    BaseInfo,
    BrokerInfoStrategy,
    StrategyListItem,
    StrategySettings,
    UserStrategy,
)
from src.models.rebalance import (
    RebalanceResult,
    RebalanceActionResult,
    RebalanceErrorResult,
    RebalancePreviewResponse,
)
from src.db.models.brokers_account import BrokersAccount
from src.db.models.users_strategy import UsersStrategy
from src.db.repositories.users_strategy_repository import UsersStrategyRepository
from src.services.broker import BrokerAccountNotFoundError

logger = logging.getLogger(__name__)


class StrategyNotFoundError(Exception):
    """Стратегия не найдена у пользователя."""


class AccountDeletedError(Exception):
    """Счёт стратегии помечен удалённым — операции по нему недоступны."""


def _wrap_account_errors(func):
    """Счёт удалён у брокера — единая ошибка вместо сырой BrokerAccountNotFoundError.

    strategy_id достаём из связанных аргументов: он есть у всех обёрнутых методов.
    """
    sig = signature(func)

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except BrokerAccountNotFoundError as exc:
            bound = sig.bind_partial(*args, **kwargs)
            strategy_id = bound.arguments.get("strategy_id", "?")
            raise AccountDeletedError(
                f"Account of strategy {strategy_id} not found in broker"
            ) from exc
    return wrapper


def _empty_portfolio_state():
    """Пустое состояние портфеля: счёт недоступен, считать не по чему."""
    return [], 0.0, 0.0, None


class _StrategySnapshot:
    """Плоский снимок стратегии до любых commit/rollback в той же сессии.

    replace_all/index replace делают commit/rollback тем же AsyncSession:
    rollback всегда expire-ит все ORM-объекты сессии, и последующий синхронный
    доступ к strategy.delta / strategy.brokers_account... в async падает
    MissingGreenlet (пример — GET /users/me 500 после IntegrityError refresh).
    Поэтому всё нужное копируем в plain-поля до первого
    _get_composition_by_snapshot / _get_directory_by_snapshot, дальше ORM-объект
    не трогаем.
    """

    __slots__ = (
        "strategy_id",
        "delta",
        "min_lots_to_keep",
        "max_cash",
        "commission",
        "broker_token_encrypted",
        "sandbox",
        "broker_id",
        "broker_name",
        "account_id",
        "account_name",
        "brokers_account_id",
        "account_deleted",
        "index_id",
        "index_name",
        "composition_tradedate",
    )

    def __init__(self, strategy):
        brokers_account = strategy.brokers_account
        users_broker = brokers_account.users_broker
        index_row = strategy.stock_markets_index
        self.strategy_id = strategy.id
        self.delta = strategy.delta
        self.min_lots_to_keep = strategy.min_lots_to_keep
        self.max_cash = strategy.max_cash
        self.commission = users_broker.commission
        self.broker_token_encrypted = users_broker.broker_token
        self.sandbox = users_broker.sandbox
        self.broker_id = users_broker.id
        self.broker_name = users_broker.broker_name
        self.account_id = brokers_account.account_id
        self.account_name = brokers_account.account_name
        self.brokers_account_id = brokers_account.id
        self.account_deleted = brokers_account.deleted_at is not None
        self.index_id = index_row.id
        self.index_name = index_row.index_name
        self.composition_tradedate = getattr(
            index_row, "composition_tradedate", None
        )


def _snapshot_strategy(strategy) -> _StrategySnapshot:
    return _StrategySnapshot(strategy)


def _broker_info(brokers_account) -> BrokerInfoStrategy:
    """Карточка брокера+счёта для ответов API: полная и лёгкая версии совпадают."""
    users_broker = brokers_account.users_broker
    return BrokerInfoStrategy(
        id=str(users_broker.id),
        name=users_broker.broker_name,
        account=BaseInfo(
            id=str(brokers_account.account_id),
            name=brokers_account.account_name,
        ),
        commission=users_broker.commission,
    )


def _to_action_results(actions) -> list:
    """Доменные Action -> плоские результаты для API-ответа."""
    return [
        RebalanceActionResult(
            type=action.type,
            ticker=action.share.ticker if action.share else None,
            quantity=action.quantity,
        )
        for action in actions
    ]


def build_portfolio_manager_for_account(brokers_account: BrokersAccount, factory: Callable):
    """Собрать PortfolioManager для счёта брокера.

    Токен резолвим и расшифровываем здесь, на сервисном слое, и инжектим в
    доменное ядро — PortfolioManager не знает ни про БД, ни про шифрование.
    Используется и API-сервисами, и планировщиком.
    """
    users_broker = brokers_account.users_broker
    broker_token = decrypt_token(users_broker.broker_token)

    return factory(
        broker_token=broker_token,
        account_id=brokers_account.account_id,
        sandbox=users_broker.sandbox,
    )


class UserService:
    def __init__(self, strategy_repo: UsersStrategyRepository,
                 portfolio_manager_factory: Callable,
                 index_sync: IndexSyncService, instrument_service: InstrumentService):
        self.strategy_repo = strategy_repo
        self.portfolio_manager_factory = portfolio_manager_factory
        self.index_sync = index_sync
        self.instrument_service = instrument_service

    def _build_portfolio_manager(self, strategy: UsersStrategy):
        return build_portfolio_manager_for_account(
            strategy.brokers_account, self.portfolio_manager_factory
        )

    def _build_portfolio_manager_from_snapshot(self, snapshot: _StrategySnapshot):
        """Менеджер по снимку: ORM после rollback не трогаем.

        Идём через build_portfolio_manager_for_account с лёгким namespace,
        чтобы моки этой функции в тестах продолжали работать.
        """
        brokers_account = SimpleNamespace(
            id=snapshot.brokers_account_id,
            account_id=snapshot.account_id,
            account_name=snapshot.account_name,
            deleted_at=None if not snapshot.account_deleted else True,
            users_broker=SimpleNamespace(
                id=snapshot.broker_id,
                broker_name=snapshot.broker_name,
                broker_token=snapshot.broker_token_encrypted,
                commission=snapshot.commission,
                sandbox=snapshot.sandbox,
            ),
        )
        return build_portfolio_manager_for_account(
            brokers_account, self.portfolio_manager_factory
        )

    async def _get_composition_by_snapshot(
        self,
        snapshot: _StrategySnapshot,
        cache: dict[uuid.UUID, CompositionSnapshot] | None = None,
    ):
        """Состав по снимку: лёгкий namespace вместо expired ORM-строки индекса.

        cache — кэш на время запроса: стратегии часто делят один индекс.
        """
        if cache is not None and snapshot.index_id in cache:
            return cache[snapshot.index_id]

        index_row = SimpleNamespace(
            id=snapshot.index_id,
            index_name=snapshot.index_name,
            composition_tradedate=snapshot.composition_tradedate,
        )
        composition = await self.index_sync.ensure_composition(
            self.strategy_repo.session, index_row
        )
        if cache is not None:
            cache[snapshot.index_id] = composition
        return composition

    async def _get_directory_by_snapshot(
        self,
        snapshot: _StrategySnapshot,
        tickers: set[str],
        cache: dict[bool, InstrumentDirectory] | None = None,
    ):
        """Справочник по снимку: токен расшифровываем здесь, а не для всех стратегий.

        cache — кэш на время запроса по контуру (sandbox): первый вызов уже
        проверил свежесть и наличие тикеров, повторно таблицу не читаем.
        """
        if cache is not None:
            cached = cache.get(snapshot.sandbox)
            if cached is not None and tickers <= set(cached.by_ticker):
                return cached

        portfolio_manager = self._build_portfolio_manager_from_snapshot(snapshot)
        directory = await self.instrument_service.ensure_directory(
            self.strategy_repo.session,
            decrypt_token(snapshot.broker_token_encrypted),
            snapshot.sandbox,
            must_contain=tickers,
            broker=portfolio_manager.broker,
        )
        if cache is not None:
            cache[snapshot.sandbox] = directory
        return directory

    async def get_user_strategies(self, user) -> List[UserStrategy]:
        strategies = await self.strategy_repo.get_user_strategies(user.id)
        # Снимаем всё нужное с ORM до первого commit/rollback в сессии:
        # _load каждой стратегии может сделать rollback (refresh справочника
        # или состава), который expire-ит все остальные стратегии той же сессии.
        snapshots = [_snapshot_strategy(strategy) for strategy in strategies]

        # Кэши на время запроса: справочник — по контуру, состав — по индексу.
        directories: dict[bool, InstrumentDirectory] = {}
        compositions: dict[uuid.UUID, CompositionSnapshot] = {}

        result = []
        for snapshot in snapshots:
            if snapshot.account_deleted:
                # По удалённому счёту в брокера не ходим — портфель недоступен.
                state = (*_empty_portfolio_state(), True)
                account_deleted = True
            else:
                try:
                    state = await self._load_strategy_preview_by_snapshot(
                        snapshot,
                        directories=directories,
                        compositions=compositions,
                    )
                    account_deleted = state[4]
                except (ValueError, InvalidToken) as exc:
                    # Одна «пустая» стратегия не должна ронять весь список.
                    logger.warning(
                        "Стратегия %s: расчёт невозможен: %s",
                        snapshot.strategy_id, exc,
                    )
                    state = (*_empty_portfolio_state(), False)
                    account_deleted = False

            positions, current_free_cash, free_cash_after, index_date, _ = state
            result.append(
                self._to_user_strategy_from_snapshot(
                    snapshot, positions, current_free_cash,
                    free_cash_after, index_date, account_deleted,
                )
            )
        return result

    async def _load_strategy_preview_by_snapshot(
        self,
        snapshot: _StrategySnapshot,
        directories: dict[bool, InstrumentDirectory] | None = None,
        compositions: dict[uuid.UUID, CompositionSnapshot] | None = None,
    ):
        """Превью по снимку: ORM после rollback не трогаем (MissingGreenlet)."""
        portfolio_manager = self._build_portfolio_manager_from_snapshot(snapshot)
        try:
            composition = await self._get_composition_by_snapshot(
                snapshot, compositions
            )
            directory = await self._get_directory_by_snapshot(
                snapshot, composition.tickers, directories
            )
            # calculate_rebalance ходит в брокера синхронно (блокирующий gRPC),
            # поэтому уводим его в threadpool, чтобы не блокировать event loop.
            # Состав и справочник уже загружены выше (асинхронно).
            # Параметры собраны из снимка до threadpool: доступ к ORM внутри
            # треда тоже был бы MissingGreenlet.
            params = BalancerParams.from_snapshot(snapshot)
            rebalance = await run_in_threadpool(
                portfolio_manager.calculate_rebalance,
                snapshot.index_name,
                params,
                composition,
                directory=directory,
            )
        except BrokerAccountNotFoundError:
            return * _empty_portfolio_state(), True
        return (
            rebalance.positions,
            rebalance.current_free_cash,
            rebalance.free_cash,
            rebalance.index_date,
            False,
        )

    @staticmethod
    def _to_user_strategy_from_snapshot(
        snapshot: _StrategySnapshot, positions, current_free_cash, free_cash_after,
        index_date, account_deleted,
    ) -> UserStrategy:
        return UserStrategy(
            id=str(snapshot.strategy_id),
            broker_info=BrokerInfoStrategy(
                id=str(snapshot.broker_id),
                name=snapshot.broker_name,
                account=BaseInfo(
                    id=str(snapshot.account_id),
                    name=snapshot.account_name,
                ),
                commission=snapshot.commission,
            ),
            index_info=BaseInfo(
                id=str(snapshot.index_id),
                name=snapshot.index_name,
            ),
            portfolio=positions,
            free_cash=current_free_cash,
            free_cash_after=free_cash_after,
            index_date=index_date,
            settings=StrategySettings(
                max_cash=snapshot.max_cash,
                delta=snapshot.delta,
                min_lots_to_keep=snapshot.min_lots_to_keep,
            ),
            account_deleted=account_deleted,
        )

    async def list_strategies(self, user) -> List[StrategyListItem]:
        """Лёгкий список стратегий без похода к брокеру — для меню бота."""
        strategies = await self.strategy_repo.get_user_strategies(user.id)

        return [
            StrategyListItem(
                id=str(strategy.id),
                broker_info=_broker_info(strategy.brokers_account),
                index_info=BaseInfo(
                    id=str(strategy.stock_markets_index.id),
                    name=strategy.stock_markets_index.index_name,
                ),
                brokers_account_id=str(strategy.brokers_account.id),
                account_deleted=strategy.brokers_account.deleted_at is not None,
            )
            for strategy in strategies
        ]

    async def _get_active_strategy(self, user, strategy_id) -> UsersStrategy:
        strategy = await self.strategy_repo.get_user_strategy(user.id, strategy_id)
        if strategy is None:
            raise StrategyNotFoundError(f"Strategy {strategy_id} not found for user {user.id}")

        if strategy.brokers_account.deleted_at is not None:
            raise AccountDeletedError(
                f"Account of strategy {strategy_id} is marked as deleted"
            )

        return strategy

    @_wrap_account_errors
    async def calculate_strategy_rebalance(self, user, strategy_id) -> RebalancePreviewResponse:
        """Превью балансировки: план действий без исполнения."""
        strategy = await self._get_active_strategy(user, strategy_id)
        snapshot = _snapshot_strategy(strategy)
        portfolio_manager = self._build_portfolio_manager_from_snapshot(snapshot)

        composition = await self._get_composition_by_snapshot(snapshot)
        directory = await self._get_directory_by_snapshot(snapshot, composition.tickers)
        preview = await run_in_threadpool(
            portfolio_manager.calculate_rebalance,
            snapshot.index_name,
            BalancerParams.from_snapshot(snapshot),
            composition,
            directory=directory,
        )

        actions = _to_action_results(preview.actions)

        return RebalancePreviewResponse(
            portfolio=preview.positions,
            free_cash=preview.current_free_cash,
            free_cash_after=preview.free_cash,
            actions=actions,
            index_date=preview.index_date,
        )

    async def execute_strategy_rebalance(
        self, user, strategy_id, actions
    ) -> RebalanceResult:
        """Исполнить готовый план клиента по стратегии пользователя.

        :param actions: список PlannedAction — исполняется как есть, без пересчёта.
            Пустой список — валидный no-op: ничего не считаем и не исполняем.
        """
        strategy = await self._get_active_strategy(user, strategy_id)
        success_action_list, error_action_list = await self._execute_planned(
            strategy, strategy_id, actions
        )

        # Доменные Action/Error не отдаём наружу как есть: внутри них сырые
        # объекты SDK, которые не сериализуются в JSON.
        success = _to_action_results(success_action_list)

        errors = []
        for error in error_action_list:
            action = error.data if isinstance(error.data, Action) else None
            errors.append(
                RebalanceErrorResult(
                    type=action.type if action else None,
                    ticker=action.share.ticker if action and action.share else None,
                    quantity=action.quantity if action else None,
                    description=error.description,
                )
            )

        return RebalanceResult(
            success=success,
            errors=errors,
        )

    @_wrap_account_errors
    async def _execute_planned(self, strategy, strategy_id, actions):
        """Исполнить готовый план клиента без пересчёта.

        Тикеры резолвятся в Share через справочник; неизвестный тикер —
        запись в errors, остальные исполняются. Достаточность позиции и денег
        проверяет брокер: отклонённые ордера падают в errors с его текстом.
        """
        snapshot = _snapshot_strategy(strategy)
        portfolio_manager = self._build_portfolio_manager_from_snapshot(snapshot)
        directory = await self._get_directory_by_snapshot(
            snapshot, {action.ticker for action in actions}
        )

        planned: list[Action] = []
        errors: list = []
        for action in actions:
            share = portfolio_manager.broker.find_share(
                action.ticker, "ticker", directory=directory
            )
            if share is None:
                # Тикер сохраняем в ошибке через лёгкую заглушку: uid для
                # ордера всё равно нет, исполнять нечего.
                errors.append(
                    DomainError(
                        source="ShadowTrader",
                        source_data=None,
                        data=Action(
                            type=action.type,
                            quantity=action.quantity,
                            share=SimpleNamespace(ticker=action.ticker, uid=None),
                        ),
                        description=f"Unknown ticker: {action.ticker}",
                    )
                )
                continue
            planned.append(Action(type=action.type, quantity=action.quantity, share=share))

        def _execute():
            return portfolio_manager.execute_actions(planned)

        success_action_list, error_action_list = await run_in_threadpool(_execute)

        return success_action_list, error_action_list + errors
