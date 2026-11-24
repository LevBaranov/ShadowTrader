import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class IndexComposition(Base):

    __tablename__ = 'index_composition'
    __table_args__ = (
        UniqueConstraint('index_id', 'ticker', name='uq_index_composition_index_ticker'),
        CheckConstraint('weight >= 0', name='ck_index_composition_weight_non_negative'),
    )

    index_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('stock_markets_index.id', ondelete='CASCADE'), nullable=False
    )
    ticker: Mapped[str] = mapped_column(nullable=False)
    shortname: Mapped[str | None] = mapped_column(nullable=True)
    # Вес бумаги в индексе, процентов (как отдаёт Мосбиржа).
    weight: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    # Торговая дата, за которую взят состав.
    tradedate: Mapped[date] = mapped_column(nullable=False)

    index: Mapped["StockMarketsIndex"] = relationship(
        "StockMarketsIndex",
        back_populates="compositions",
    )
