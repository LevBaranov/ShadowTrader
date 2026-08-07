from typing import List

from starlette.concurrency import run_in_threadpool

from src.core.crypto import decrypt_token
from src.models.action import Action
from src.models.balancer_params import BalancerParams
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


class StrategyNotFoundError(Exception):
    """Стратегия не найдена у пользователя."""


class AccountDeletedError(Exception):
    """Счёт стратегии помечен удалённым — операции по нему недоступны."""


def build_portfolio_manager_for_account(brokers_account: BrokersAccount, factory):
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
    def __init__(self, strategy_repo: UsersStrategyRepository, portfolio_manager_factory):
        self.strategy_repo = strategy_repo
        self.portfolio_manager_factory = portfolio_manager_factory

    def _build_portfolio_manager(self, strategy: UsersStrategy):
        return build_portfolio_manager_for_account(
            strategy.brokers_account, self.portfolio_manager_factory
        )

    async def get_user_strategies(self, user) -> List[UserStrategy]:
        strategies = await self.strategy_repo.get_user_strategies(user.id)

        result = []
        for strategy in strategies:
            broker_account = strategy.brokers_account
            users_broker = broker_account.users_broker

            account_id = broker_account.account_id
            account_name = broker_account.account_name
            broker_name = users_broker.broker_name
            index_id = strategy.stock_markets_index.id
            index_name = strategy.stock_markets_index.index_name

            account_deleted = broker_account.deleted_at is not None

            if account_deleted:
                # По удалённому счёту в брокера не ходим — портфель недоступен.
                positions, current_free_cash, free_cash_after = [], 0.0, 0.0
            else:
                portfolio_manager = self._build_portfolio_manager(strategy)
                try:
                    # calculate_rebalance ходит в брокера/MOEX синхронно (блокирующий gRPC/HTTP),
                    # поэтому уводим его в threadpool, чтобы не блокировать event loop.
                    rebalance = await run_in_threadpool(
                        portfolio_manager.calculate_rebalance,
                        index_name,
                        BalancerParams.from_strategy(strategy),
                    )
                except BrokerAccountNotFoundError:
                    # Счёт удалён у брокера, но deleted_at ещё не проставлен
                    # (синхронизация счетов не выполнялась) — стратегию
                    # показываем неактивной, не роняя весь ответ.
                    account_deleted = True
                    positions, current_free_cash, free_cash_after = [], 0.0, 0.0
                else:
                    positions = rebalance.positions
                    current_free_cash = rebalance.current_free_cash
                    free_cash_after = rebalance.free_cash

            result.append(
                UserStrategy(
                    id=str(strategy.id),
                    broker_info=BrokerInfoStrategy(
                        id=str(users_broker.id),
                        name=broker_name,
                        account=BaseInfo(
                            id=str(account_id),
                            name=account_name,
                        ),
                        commission=users_broker.commission,
                    ),
                    index_info=BaseInfo(
                        id=str(index_id),
                        name=index_name
                    ),
                    portfolio=positions,
                    free_cash=current_free_cash,
                    free_cash_after=free_cash_after,
                    settings=StrategySettings(
                        max_cash=strategy.max_cash,
                        delta=strategy.delta,
                        min_lots_to_keep=strategy.min_lots_to_keep,
                    ),
                    account_deleted=account_deleted,
                )
            )
        return result

    async def list_strategies(self, user) -> List[StrategyListItem]:
        """Лёгкий список стратегий без похода к брокеру — для меню бота."""
        strategies = await self.strategy_repo.get_user_strategies(user.id)

        return [
            StrategyListItem(
                id=str(strategy.id),
                broker_info=BrokerInfoStrategy(
                    id=str(strategy.brokers_account.users_broker.id),
                    name=strategy.brokers_account.users_broker.broker_name,
                    account=BaseInfo(
                        id=str(strategy.brokers_account.account_id),
                        name=strategy.brokers_account.account_name,
                    ),
                    commission=strategy.brokers_account.users_broker.commission,
                ),
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

    async def calculate_strategy_rebalance(self, user, strategy_id) -> RebalancePreviewResponse:
        """Превью балансировки: план действий без исполнения."""
        strategy = await self._get_active_strategy(user, strategy_id)

        index_name = strategy.stock_markets_index.index_name
        portfolio_manager = self._build_portfolio_manager(strategy)

        try:
            preview = await run_in_threadpool(
                portfolio_manager.calculate_rebalance,
                index_name,
                BalancerParams.from_strategy(strategy),
            )
        except BrokerAccountNotFoundError as exc:
            raise AccountDeletedError(
                f"Account of strategy {strategy_id} not found in broker"
            ) from exc

        actions = [
            RebalanceActionResult(
                type=action.type,
                ticker=action.share.ticker if action.share else None,
                quantity=action.quantity,
            )
            for action in preview.actions
        ]

        return RebalancePreviewResponse(
            portfolio=preview.positions,
            free_cash=preview.current_free_cash,
            free_cash_after=preview.free_cash,
            actions=actions,
        )

    async def execute_strategy_rebalance(self, user, strategy_id) -> RebalanceResult:
        """Рассчитать и исполнить балансировку по конкретной стратегии пользователя."""
        strategy = await self._get_active_strategy(user, strategy_id)

        index_name = strategy.stock_markets_index.index_name
        portfolio_manager = self._build_portfolio_manager(strategy)

        params = BalancerParams.from_strategy(strategy)

        def _calculate_and_execute():
            # Оба вызова синхронные и должны выполниться в одном потоке:
            # calculate_rebalance наполняет self.actions, которые исполняет execute_actions.
            portfolio_manager.calculate_rebalance(index_name, params)
            return portfolio_manager.execute_actions()

        try:
            success_action_list, error_action_list = await run_in_threadpool(_calculate_and_execute)
        except BrokerAccountNotFoundError as exc:
            raise AccountDeletedError(
                f"Account of strategy {strategy_id} not found in broker"
            ) from exc

        # Доменные Action/Error не отдаём наружу как есть: внутри них сырые
        # объекты SDK, которые не сериализуются в JSON.
        success = [
            RebalanceActionResult(
                type=action.type,
                ticker=action.share.ticker if action.share else None,
                quantity=action.quantity,
            )
            for action in success_action_list
        ]

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
