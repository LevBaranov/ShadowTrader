from decimal import Decimal

from pydantic import Field

from src.models.api_base import BaseApiModel
from src.models.strategies_type import StrategiesType

# delta — доля, а не проценты: 0.05 = 5 % допустимого отклонения от веса в индексе.
# lt=1 отсекает случай, когда клиент прислал проценты вместо доли.
DeltaField = Field(ge=0, lt=1)


class CreateStrategyRequest(BaseApiModel):
    brokers_account_id: str
    stock_markets_index_id: str
    strategy_type: StrategiesType = StrategiesType.SHARE
    # Неснижаемый остаток денег на счёте: балансировщик его не тратит.
    max_cash: int = Field(default=0, ge=0)
    # None — оставить значение по умолчанию из БД (0.05 и 1).
    delta: Decimal | None = Field(default=None, ge=0, lt=1)
    min_lots_to_keep: int | None = Field(default=None, ge=0)


class UpdateStrategyRequest(BaseApiModel):
    """Изменяемые настройки стратегии. Счёт и индекс не меняются — это новая стратегия.

    Комиссии здесь нет: это тариф брокера, см. PATCH /brokers/{id}.
    """
    max_cash: int = Field(ge=0)
    delta: Decimal = DeltaField
    min_lots_to_keep: int = Field(ge=0)


class StrategyResponse(BaseApiModel):
    id: str
    brokers_account_id: str
    stock_markets_index_id: str
    strategy_type: StrategiesType
    max_cash: int = 0
    # Доля: 0.05 = 5 %. Проценты для пользователя считает клиент.
    delta: Decimal
    min_lots_to_keep: int
