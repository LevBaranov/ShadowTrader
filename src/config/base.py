from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime


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
    max_cash: int


class TelegramConfig(BaseModel):
    token: str


class UserLinksConfig(BaseModel):
    broker_account_id: str
    broker_account_name: str
    index_name: str


class UserScheduleConfig(BaseModel):
    last_run: datetime = None
    rebalance_frequency: str = None


class UserConfig(BaseModel):
    telegram_id: int
    links: UserLinksConfig = None
    schedule: UserScheduleConfig = None


class LoggingConfig(BaseModel):
    enabled: bool = True
    path: str


class SchedulerConfig(BaseModel):
    timeout_in_sec: int


class AppConfig(BaseModel):
    telegram: TelegramConfig
    broker: BrokerConfig
    stock_market: StockMarketConfig
    balancer: BalancerConfig
    users: List[UserConfig] = []
    logging: LoggingConfig
    scheduler: SchedulerConfig

