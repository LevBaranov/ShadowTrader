from typing import List

from src.models.api_base import BaseApiModel
from src.models.rebalance import PortfolioPosition

class BaseInfo(BaseApiModel):
    id: str
    name: str

class BrokerInfoStrategy(BaseInfo):
    account: BaseInfo

class UserStrategy(BaseApiModel):
    id: str
    broker_info: BrokerInfoStrategy
    index_info: BaseInfo
    portfolio: List[PortfolioPosition | None]
    # Свободные средства сейчас и сколько останется после применения стратегии.
    free_cash: float
    free_cash_after: float
    # Счёт стратегии помечен удалённым у брокера — балансировка недоступна.
    account_deleted: bool = False

class CurrentUserInfo(BaseApiModel):
    id: str
    email: str
    strategies: List[UserStrategy]


class RebalanceRequest(BaseApiModel):
    strategy_id: str


class LoginRequest(BaseApiModel):
    email: str
    password: str

class LoginSuccess(BaseApiModel):
    access_token: str
    token_type: str

