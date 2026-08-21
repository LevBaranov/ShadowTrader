import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base

from src.models.strategies_type import StrategiesType

# Прежние значения [balancer].delta и .min_lots_to_keep из toml.
DEFAULT_DELTA = Decimal("0.05")
DEFAULT_MIN_LOTS_TO_KEEP = 1

class UsersStrategy(Base):

    __tablename__ = 'users_strategy'

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    strategy_type: Mapped[StrategiesType] = mapped_column(nullable=False)
    brokers_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('brokers_account.id'), nullable=False)
    stock_markets_index_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('stock_markets_index.id'), nullable=False)

    # Неснижаемый остаток денег на счёте: балансировщик не тратит эту сумму на
    # покупки. 0 — тратить весь свободный кэш (прежнее поведение).
    # Раньше жил в toml как [balancer].max_cash, теперь настройка пользователя.
    max_cash: Mapped[int] = mapped_column(nullable=False, default=0, server_default='0')

    # Допустимое отклонение веса бумаги от веса в индексе, долей: 0.05 = 5 %.
    # Пока отклонение в пределах delta, бумагу не трогаем.
    delta: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
        default=DEFAULT_DELTA,
        server_default=str(DEFAULT_DELTA),
    )

    # Сколько лотов бумаги оставлять при продаже, даже если вес превышен.
    min_lots_to_keep: Mapped[int] = mapped_column(
        nullable=False,
        default=DEFAULT_MIN_LOTS_TO_KEEP,
        server_default=str(DEFAULT_MIN_LOTS_TO_KEEP),
    )


    user: Mapped["User"] = relationship(
        "User",
        back_populates="users_strategy",
        lazy="selectin"
    )

    brokers_account: Mapped["BrokersAccount"] = relationship(
        "BrokersAccount",
        back_populates="users_strategy",
        lazy="selectin"
    )

    stock_markets_index: Mapped["StockMarketsIndex"] = relationship(
        "StockMarketsIndex",
        back_populates="users_strategy",
        lazy="selectin"
    )
