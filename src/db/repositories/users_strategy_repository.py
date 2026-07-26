import uuid
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Iterable, List, Optional, Set

from src.db.models.users_strategy import UsersStrategy
from src.models.strategies_type import StrategiesType

class UsersStrategyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_strategies(self, user_id: uuid.UUID) -> List[UsersStrategy]:
        result = await self.session.execute(
            select(UsersStrategy).where(UsersStrategy.user_id == user_id)
        )

        return [ r for r in result.scalars().all() ]

    async def get_user_strategy(
        self, user_id: uuid.UUID, strategy_id: uuid.UUID
    ) -> Optional[UsersStrategy]:
        result = await self.session.execute(
            select(UsersStrategy).where(
                UsersStrategy.user_id == user_id,
                UsersStrategy.id == strategy_id,
            )
        )
        return result.scalar_one_or_none()

    async def exists_for_account(self, brokers_account_id: uuid.UUID) -> bool:
        """Есть ли уже стратегия на этом счёте (на счёт допускается одна стратегия)."""
        result = await self.session.execute(
            select(UsersStrategy.id).where(
                UsersStrategy.brokers_account_id == brokers_account_id
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def get_busy_account_ids(
        self, account_ids: Iterable[uuid.UUID]
    ) -> Set[uuid.UUID]:
        """Из переданных счетов вернуть те, на которых уже есть стратегия."""
        ids = list(account_ids)
        if not ids:
            return set()

        result = await self.session.execute(
            select(UsersStrategy.brokers_account_id).where(
                UsersStrategy.brokers_account_id.in_(ids)
            )
        )
        return set(result.scalars().all())

    async def create(
        self,
        user_id: uuid.UUID,
        strategy_type: StrategiesType,
        brokers_account_id: uuid.UUID,
        stock_markets_index_id: uuid.UUID,
    ) -> UsersStrategy:
        strategy = UsersStrategy(
            user_id=user_id,
            strategy_type=strategy_type,
            brokers_account_id=brokers_account_id,
            stock_markets_index_id=stock_markets_index_id,
        )
        self.session.add(strategy)
        await self.session.commit()
        await self.session.refresh(strategy)
        return strategy

    async def delete(self, user_id: uuid.UUID, strategy_id: uuid.UUID) -> bool:
        """Удалить стратегию пользователя. Возвращает True, если что-то удалено."""
        result = await self.session.execute(
            delete(UsersStrategy).where(
                UsersStrategy.user_id == user_id,
                UsersStrategy.id == strategy_id,
            )
        )
        await self.session.commit()
        return result.rowcount > 0