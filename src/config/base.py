from pydantic import BaseModel
from typing import Optional, Dict, List


class BrokerConfig(BaseModel):
    token: str
    sandbox_mode: bool = True
    log_file: str


class StockMarketConfig(BaseModel):
    index_name: str = "IMOEX"
    limit: int = 100
    base_url: str = "https://iss.moex.com/iss"


class BalancerConfig(BaseModel):
    delta: float = 0.05
    commission: float = 0.003
    min_lots_to_keep: int = 1


class TelegramConfig(BaseModel):
    token: str


class UserConfig(BaseModel):
    telegram_id: int


class LoggingConfig(BaseModel):
    enabled: bool = True
    path: str


class AppConfig(BaseModel):
    telegram: TelegramConfig
    broker: BrokerConfig
    stock_market: StockMarketConfig
    balancer: BalancerConfig
    users: List[UserConfig] = []
    logging: LoggingConfig

