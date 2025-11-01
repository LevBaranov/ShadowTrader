from pydantic import BaseModel
from typing import List
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


class BrokerAccountConfig(BaseModel):
    broker_account_id: str = None
    broker_account_name: str = None


class UserIndexBindingsConfig(BrokerAccountConfig):
    index_name: str = None


class UserScheduleConfig(BaseModel):
    last_run: datetime = None
    rebalance_frequency: str = None
    enable_bond_reminder: bool = False
    bond_reminder_last_run: datetime = None


class UserConfig(BaseModel):
    telegram_id: int
    index_bindings: UserIndexBindingsConfig = None
    schedule: UserScheduleConfig = None
    bonds_account: BrokerAccountConfig = None


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

