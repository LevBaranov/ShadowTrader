import uuid
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base

from src.models.strategies_type import StrategiesType

class UsersStrategy(Base):

    __tablename__ = 'users_strategy'

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    strategy_type: Mapped[StrategiesType] = mapped_column(nullable=False)
    brokers_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('brokers_account.id'), nullable=False)
    stock_markets_index_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('stock_markets_index.id'), nullable=False)


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
