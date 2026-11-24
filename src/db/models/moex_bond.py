from datetime import date, datetime

from sqlalchemy import Date, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.database import Base


class MoexBond(Base):
    """Строка справочника облигаций Мосбиржи, ежедневно синхронизируемая.

    Общий словарь данных MOEX: даты оферт/колл-опционов, цена выкупа и номинал.
    Тикер security (SECID) — натуральный ключ.
    """

    __tablename__ = 'moex_bonds'

    secid: Mapped[str] = mapped_column(nullable=False)
    short_name: Mapped[str | None] = mapped_column(nullable=True)
    board_name: Mapped[str | None] = mapped_column(nullable=True)
    lot_value: Mapped[float | None] = mapped_column(nullable=True)
    offer_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    call_option_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    put_option_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    buy_back_price: Mapped[float | None] = mapped_column(nullable=True)
    isin: Mapped[str | None] = mapped_column(nullable=True)
    # Дата, когда открывается окно подачи заявок на оферту (bondization).
    offer_start_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
