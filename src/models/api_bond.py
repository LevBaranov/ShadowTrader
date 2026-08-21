from datetime import date

from src.models.api_base import BaseApiModel


class BondEventResponse(BaseApiModel):
    """Предстоящее событие по облигации."""
    # Имя enum'а BondEventType: OFFER | CALL_OPTION.
    type: str
    date: date


class BondWithEventsResponse(BaseApiModel):
    """Облигация на счёте, по которой впереди есть оферта или колл-опцион."""
    ticker: str
    name: str | None = None
    figi: str | None = None
    # Количество бумаг на счёте.
    quantity: int = 0
    events: list[BondEventResponse]
