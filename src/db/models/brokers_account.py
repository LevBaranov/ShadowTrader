import uuid
from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base

class BrokersAccount(Base):

    __tablename__ = 'brokers_account'

    users_broker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users_broker.id'), nullable=False)
    account_name: Mapped[str]
    account_id: Mapped[str]
    # Закрытые у брокера счета не удаляем (на них ссылаются стратегии),
    # а проставляем дату удаления. NULL — счёт живой.
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)

    users_broker: Mapped["UsersBroker"] = relationship(
        "UsersBroker",
        back_populates="brokers_account",
        lazy="selectin"
    )

    users_strategy: Mapped["UsersStrategy"] = relationship(
        "UsersStrategy",
        back_populates="brokers_account",
        cascade="all, delete-orphan"
    )