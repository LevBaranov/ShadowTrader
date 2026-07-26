import logging
import uuid
from datetime import timedelta
from typing import List

from starlette.concurrency import run_in_threadpool

from src.db.models.stock_market_index import StockMarketsIndex
from src.db.models.users_strategy import UsersStrategy
from src.db.repositories.brokers_account_repository import BrokersAccountRepository
from src.db.repositories.stock_markets_index_repository import StockMarketsIndexRepository
from src.db.repositories.users_strategy_repository import UsersStrategyRepository
from src.models.error import Error
from src.models.stock_markets_name import StockMarketsNames
from src.models.strategies_type import StrategiesType

logger = logging.getLogger(__name__)

# Как часто обновлять справочник индексов с биржи.
INDEX_SYNC_MAX_AGE = timedelta(days=7)


class StrategyValidationError(Exception):
    """Некорректные данные для создания стратегии (чужой/несуществующий аккаунт или индекс)."""


class StrategyNotFoundError(Exception):
    """Стратегия не найдена у пользователя."""


class StrategyService:
    def __init__(
        self,
        strategy_repo: UsersStrategyRepository,
        accounts_repo: BrokersAccountRepository,
        index_repo: StockMarketsIndexRepository,
        stock_market_client_factory=None,
    ):
        self.strategy_repo = strategy_repo
        self.accounts_repo = accounts_repo
        self.index_repo = index_repo
        # Фабрика клиента биржи (напр. Moex) для обновления справочника индексов.
        self.stock_market_client_factory = stock_market_client_factory

    async def list_indices(self) -> List[StockMarketsIndex]:
        """Список индексов из БД. Если справочник старше INDEX_SYNC_MAX_AGE —
        сначала обновляем его с биржи (пропавшим индексам проставляется deleted_at)."""
        if self.stock_market_client_factory and await self.index_repo.is_stale(INDEX_SYNC_MAX_AGE):
            try:
                client = self.stock_market_client_factory()
                # Запрос к бирже синхронный (requests) — уводим в threadpool.
                indices = await run_in_threadpool(client.get_indices)
            except Error as exc:
                # Биржа недоступна — отдаём то, что есть в БД, попробуем в следующий раз.
                logger.warning("Не удалось обновить список индексов с Мосбиржи: %s", exc)
            else:
                await self.index_repo.sync(StockMarketsNames.MOEX, indices)

        return await self.index_repo.list_all()

    async def create_strategy(
        self,
        user,
        brokers_account_id: uuid.UUID,
        stock_markets_index_id: uuid.UUID,
        strategy_type: StrategiesType,
    ) -> UsersStrategy:
        # Аккаунт должен принадлежать пользователю.
        account = await self.accounts_repo.get_for_user(brokers_account_id, user.id)
        if account is None:
            raise StrategyValidationError("Broker account not found for user")

        # На один счёт допускается только одна стратегия.
        if await self.strategy_repo.exists_for_account(brokers_account_id):
            raise StrategyValidationError("На этом счёте уже есть стратегия")

        # Индекс должен существовать.
        index = await self.index_repo.get_by_id(stock_markets_index_id)
        if index is None:
            raise StrategyValidationError("Stock market index not found")

        return await self.strategy_repo.create(
            user_id=user.id,
            strategy_type=strategy_type,
            brokers_account_id=brokers_account_id,
            stock_markets_index_id=stock_markets_index_id,
        )

    async def delete_strategy(self, user, strategy_id: uuid.UUID) -> None:
        deleted = await self.strategy_repo.delete(user.id, strategy_id)
        if not deleted:
            raise StrategyNotFoundError(f"Strategy {strategy_id} not found for user {user.id}")
