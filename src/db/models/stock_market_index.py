from datetime import date, datetime

from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base

from src.models.stock_markets_name import StockMarketsNames

class StockMarketsIndex(Base):

    __tablename__ = 'stock_markets_index'

    stock_market: Mapped[StockMarketsNames] = mapped_column(nullable=False)
    index_name: Mapped[str] = mapped_column(nullable=False)
    # Человекочитаемое название (SHORTNAME с Мосбиржи).
    description: Mapped[str | None] = mapped_column(nullable=True)
    # Пропавшие из выдачи биржи индексы не удаляем (на них ссылаются стратегии),
    # а проставляем дату удаления. NULL — строка живая.
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # Когда последний раз обновляли состав индекса (системная задача INDEX_SYNC).
    # NULL — состав ещё ни разу не синкался.
    composition_updated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # Торговая дата, за которую взят текущий состав.
    composition_tradedate: Mapped[date | None] = mapped_column(nullable=True)

    compositions: Mapped[list["IndexComposition"]] = relationship(
        "IndexComposition",
        back_populates="index",
        cascade="all, delete-orphan",
    )

    users_strategy: Mapped["UsersStrategy"] = relationship(
        "UsersStrategy",
        back_populates="stock_markets_index",
        cascade="all, delete-orphan"
    )