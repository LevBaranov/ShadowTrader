from pydantic import BaseModel
from typing import List

from src.models.action import Action
from src.models.api_base import BaseApiModel
from src.models.error import Error


class PortfolioPosition(BaseApiModel):
    ticker: str
    name: str
    uid: str
    index_weight: float
    portfolio_weight: float
    portfolio_count: int
    offer: int | None = None


class RebalanceResult(BaseApiModel):
    success: List[Action]
    errors:  List[Error]


class RebalancePreview(BaseModel):
    actions: List[Action]
    free_cash: float

    positions: List[PortfolioPosition]




class CalculatedPosition(BaseModel):
    ticker: str
    target_weight: float
    current_weight: float

    balance: int
    lot_size: int
    last_price: float

    suggested_quantity: int | None = None
