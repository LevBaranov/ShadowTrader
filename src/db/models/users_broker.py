import uuid
import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base

from src.models.broker_names import BrokerNames

class UsersBroker(Base):

    __tablename__ = 'users_broker'

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    broker_name: Mapped[BrokerNames] = mapped_column(nullable=False)
    # Токен хранится в зашифрованном виде (см. src/core/crypto.py).
    broker_token: Mapped[str] = mapped_column(nullable=False)
    sandbox: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=sa.false())

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