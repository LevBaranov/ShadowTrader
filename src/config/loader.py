import os
import toml
from pathlib import Path
from src.config.base import AppConfig

ENV = os.getenv("APP_ENV", "prod")
CONFIG_PATH = Path(__file__).parent / "environments" / f"{ENV}.toml"


class ConfigLoader:
    config: AppConfig

    @classmethod
    def load(cls):
        data = toml.loads(CONFIG_PATH.read_text())
        cls.config = AppConfig(**data)

    # @classmethod
    # def save(cls):
    #     raw = cls.config.model_dump()
    #     CONFIG_PATH.write_text(toml.dumps(raw))
    #
    # @classmethod
    # def set_token(cls, token: str):
    #     cls.config.broker.token = token
    #     cls.save()
    #
    # @classmethod
    # def set_index(cls, index_name: str):
    #     cls.config.stock_market.index_name = index_name
    #     cls.save()


