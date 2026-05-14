from typing import List

from src.models.api_base import BaseApiModel
from src.models.rebalance import PortfolioPosition

class BaseInfo(BaseApiModel):
    id: str
    name: str

class BrokerInfoStrategy(BaseInfo):
    account: BaseInfo

class UserStrategy(BaseApiModel):
    broker_info: BrokerInfoStrategy
    index_info: BaseInfo
    portfolio: List[PortfolioPosition | None]
    free_cash: float

class CurrentUserInfo(BaseApiModel):
    id: str
    email: str
    strategies: List[UserStrategy]


class LoginRequest(BaseApiModel):
    email: str
    password: str

class LoginSuccess(BaseApiModel):
    access_token: str
    token_type: str

