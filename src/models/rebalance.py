from pydantic import BaseModel
from typing import List

from src.models.action import Action
from src.models.api_base import BaseApiModel


class PortfolioPosition(BaseApiModel):
    ticker: str
    name: str
    uid: str
    index_weight: float
    portfolio_weight: float
    portfolio_count: int
    offer: int | None = None


class RebalanceActionResult(BaseApiModel):
    """Успешно исполненное действие балансировки в API-ответе."""
    type: str
    ticker: str | None = None
    quantity: int


class RebalanceErrorResult(BaseApiModel):
    """Ошибка исполнения действия в API-ответе.

    Доменный Error таскает в себе сырые объекты SDK (RequestError и т.п.),
    которые pydantic не сериализует — наружу отдаём только плоские поля.
    """
    type: str | None = None
    ticker: str | None = None
    quantity: int | None = None
    description: str | None = None


class RebalanceResult(BaseApiModel):
    success: List[RebalanceActionResult]
    errors:  List[RebalanceErrorResult]


class RebalancePreviewResponse(BaseApiModel):
    """Превью балансировки в API: план действий без исполнения."""
    portfolio: List[PortfolioPosition]
    free_cash: float
    free_cash_after: float
    actions: List[RebalanceActionResult]


class RebalancePreview(BaseModel):
    actions: List[Action]
    # Свободные средства на счёте сейчас.
    current_free_cash: float
    # Сколько останется после применения рассчитанных действий.
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
