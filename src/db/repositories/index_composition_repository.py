import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.index_composition import IndexComposition
from src.db.models.stock_market_index import StockMarketsIndex


class IndexCompositionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_index(self, index_id: uuid.UUID) -> list[IndexComposition]:
        """Строки текущего слепка состава индекса."""
        result = await self.session.execute(
            select(IndexComposition)
            .where(IndexComposition.index_id == index_id)
            .order_by(IndexComposition.ticker)
        )
        return list(result.scalars().all())

    async def replace(
        self,
        index_id: uuid.UUID,
        tradedate: date,
        rows: list[tuple[str, str | None, Decimal]],
    ) -> None:
        """Заменить слепок состава целиком: истории не храним.

        rows — (ticker, shortname, weight). Вместе со строками обновляется
        мета синка на самом индексе.
        """
        await self.session.execute(
            delete(IndexComposition).where(IndexComposition.index_id == index_id)
        )
        self.session.add_all([
            IndexComposition(
                index_id=index_id,
                ticker=ticker,
                shortname=shortname,
                weight=weight,
                tradedate=tradedate,
            )
            for ticker, shortname, weight in rows
        ])
        # Сбрасываем удалённые/добавленные в сессию, чтобы get ниже видел свежее.
        await self.session.flush()

        index_row = await self.session.get(StockMarketsIndex, index_id)
        if index_row is not None:
            index_row.composition_updated_at = func.now()
            index_row.composition_tradedate = tradedate

        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
