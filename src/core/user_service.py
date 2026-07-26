from typing import List

from starlette.concurrency import run_in_threadpool

from src.core.crypto import decrypt_token
from src.models.action import Action
from src.models.api_user import BrokerInfoStrategy, UserStrategy, BaseInfo
from src.models.rebalance import RebalanceResult, RebalanceActionResult, RebalanceErrorResult
from src.db.models.users_strategy import UsersStrategy
from src.db.repositories.users_strategy_repository import UsersStrategyRepository


class StrategyNotFoundError(Exception):
    """Стратегия не найдена у пользователя."""


class AccountDeletedError(Exception):
    """Счёт стратегии помечен удалённым — операции по нему недоступны."""


class UserService:
    def __init__(self, strategy_repo: UsersStrategyRepository, portfolio_manager_factory):
        self.strategy_repo = strategy_repo
        self.portfolio_manager_factory = portfolio_manager_factory

    def _build_portfolio_manager(self, strategy: UsersStrategy):
        """Собрать PortfolioManager из сущности стратегии.

        Токен резолвим и расшифровываем здесь, на сервисном слое, и инжектим в
        доменное ядро — PortfolioManager не знает ни про БД, ни про шифрование.
        """
        users_broker = strategy.brokers_account.users_broker
        broker_token = decrypt_token(users_broker.broker_token)

        return self.portfolio_manager_factory(
            broker_token=broker_token,
            account_id=strategy.brokers_account.account_id,
            sandbox=users_broker.sandbox,
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
                # calculate_rebalance ходит в брокера/MOEX синхронно (блокирующий gRPC/HTTP),
                # поэтому уводим его в threadpool, чтобы не блокировать event loop.
                rebalance = await run_in_threadpool(
                    portfolio_manager.calculate_rebalance, index_name
                )
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
                    ),
                    index_info=BaseInfo(
                        id=str(index_id),
                        name=index_name
                    ),
                    portfolio=positions,
                    free_cash=current_free_cash,
                    free_cash_after=free_cash_after,
                    account_deleted=account_deleted,
                )
            )
        return result

    async def execute_strategy_rebalance(self, user, strategy_id) -> RebalanceResult:
        """Рассчитать и исполнить балансировку по конкретной стратегии пользователя."""
        strategy = await self.strategy_repo.get_user_strategy(user.id, strategy_id)
        if strategy is None:
            raise StrategyNotFoundError(f"Strategy {strategy_id} not found for user {user.id}")

        if strategy.brokers_account.deleted_at is not None:
            raise AccountDeletedError(
                f"Account of strategy {strategy_id} is marked as deleted"
            )

        index_name = strategy.stock_markets_index.index_name
        portfolio_manager = self._build_portfolio_manager(strategy)

        def _calculate_and_execute():
            # Оба вызова синхронные и должны выполниться в одном потоке:
            # calculate_rebalance наполняет self.actions, которые исполняет execute_actions.
            portfolio_manager.calculate_rebalance(index_name)
            return portfolio_manager.execute_actions()

        success_action_list, error_action_list = await run_in_threadpool(_calculate_and_execute)

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
