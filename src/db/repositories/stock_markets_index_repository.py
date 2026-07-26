import uuid
from datetime import timedelta
from typing import Iterable, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.stock_market_index import StockMarketsIndex
from src.models.stock_markets_name import StockMarketsNames


class StockMarketsIndexRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_all(self) -> List[StockMarketsIndex]:
        result = await self.session.execute(
            select(StockMarketsIndex).where(StockMarketsIndex.deleted_at.is_(None))
        )
        return list(result.scalars().all())

    async def get_by_id(self, index_id: uuid.UUID) -> Optional[StockMarketsIndex]:
        result = await self.session.execute(
            select(StockMarketsIndex).where(
                StockMarketsIndex.id == index_id,
                StockMarketsIndex.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def is_stale(self, max_age: timedelta) -> bool:
        """Пора ли обновлять справочник: нет ни одной записи, синхронизированной
        не позднее max_age назад. Записи без description не считаются —
        они созданы до появления описаний и требуют досинхронизации.
        Сравнение по времени БД, чтобы не зависеть от часов приложения."""
        result = await self.session.execute(
            select(func.count(StockMarketsIndex.id)).where(
                StockMarketsIndex.updated_at >= func.now() - max_age,
                StockMarketsIndex.description.is_not(None),
            )
        )
        return result.scalar_one() == 0

    async def sync(
        self,
        stock_market: StockMarketsNames,
        indices: Iterable[tuple[str, str]],
    ) -> None:
        """Синхронизировать справочник индексов биржи с внешним списком.

        indices — итерируемое из (index_name, description). Новые создаются,
        существующие обновляются, пропавшим проставляется deleted_at. updated_at
        бросается на всех строках явно — по нему считается свежесть справочника.
        """
        result = await self.session.execute(
            select(StockMarketsIndex).where(
                StockMarketsIndex.stock_market == stock_market
            )
        )
        existing = {row.index_name: row for row in result.scalars().all()}
        incoming = dict(indices)

        for index_name, description in incoming.items():
            row = existing.get(index_name)
            if row is None:
                self.session.add(
                    StockMarketsIndex(
                        stock_market=stock_market,
                        index_name=index_name,
                        description=description,
                    )
                )
            else:
                row.description = description
                row.deleted_at = None
                row.updated_at = func.now()

        for index_name, row in existing.items():
            if index_name not in incoming:
                if row.deleted_at is None:
                    row.deleted_at = func.now()
                row.updated_at = func.now()

        await self.session.commit()
