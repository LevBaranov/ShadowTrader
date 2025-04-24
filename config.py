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
    index_name: str = Field("IMOEX")
    limit: int = 100
    base_url: str = "https://iss.moex.com/iss"

class Settings:
    broker: BrokerConfig = BrokerConfig()
    stock_market: StockMarketConfig = StockMarketConfig()

settings = Settings()