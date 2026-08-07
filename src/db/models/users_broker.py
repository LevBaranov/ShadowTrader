import uuid
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base

from src.models.broker_names import BrokerNames

# Комиссия по умолчанию — 0,3 % (прежнее значение [balancer].commission из toml).
DEFAULT_COMMISSION = Decimal("0.003")

class UsersBroker(Base):

    __tablename__ = 'users_broker'

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    broker_name: Mapped[BrokerNames] = mapped_column(nullable=False)
    # Токен хранится в зашифрованном виде (см. src/core/crypto.py).
    broker_token: Mapped[str] = mapped_column(nullable=False)
    sandbox: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=sa.false())
    # Комиссия брокера долей: 0.003 = 0,3 %. Тариф общий для всех счетов и
    # стратегий этого брокера, поэтому настройка живёт здесь, а не на стратегии.
    # Numeric, а не Float: параметр денежный, двоичная плавающая точка не нужна.
    commission: Mapped[Decimal] = mapped_column(
        Numeric(6, 5),
        nullable=False,
        default=DEFAULT_COMMISSION,
        server_default=str(DEFAULT_COMMISSION),
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="users_broker",
        lazy="selectin"
    )

    brokers_account: Mapped["BrokersAccount"] = relationship(
        "BrokersAccount",
        back_populates="users_broker",
        cascade="all, delete-orphan"
    )