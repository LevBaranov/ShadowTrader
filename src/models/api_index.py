from src.models.api_base import BaseApiModel
from src.models.stock_markets_name import StockMarketsNames


class IndexResponse(BaseApiModel):
    id: str
    stock_market: StockMarketsNames
    index_name: str
    description: str | None = None
