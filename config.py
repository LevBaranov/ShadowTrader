from pydantic import Field
from pydantic_settings import BaseSettings

class BrokerConfig(BaseSettings):
    token: str = Field(..., env="BROKER_TOKEN")
    sandbox_mode: bool = Field(True, env="BROKER_SANDBOX_MODE")

    class Config:
        env_prefix = "BROKER_"
        env_file = ".env"
        env_file_encoding = "utf-8"

class StockMarketConfig(BaseSettings):
    index_name: str = "IMOEX"
    limit: int = 100
    base_url: str = "https://iss.moex.com/iss"

class BalancerConfig(BaseSettings):
    delta: float = 0.05
    commission: float = 0.003
    min_lots_to_keep: int = 1


class Settings:
    broker: BrokerConfig = BrokerConfig()
    stock_market: StockMarketConfig = StockMarketConfig()
    balancer: BalancerConfig = BalancerConfig()

settings = Settings()