from src.models.api_base import BaseApiModel
from src.models.strategies_type import StrategiesType


class CreateStrategyRequest(BaseApiModel):
    brokers_account_id: str
    stock_markets_index_id: str
    strategy_type: StrategiesType = StrategiesType.SHARE


class StrategyResponse(BaseApiModel):
    id: str
    brokers_account_id: str
    stock_markets_index_id: str
    strategy_type: StrategiesType
