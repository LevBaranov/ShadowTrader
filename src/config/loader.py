import os
import toml
from pathlib import Path
from src.config.base import AppConfig, UserLinksConfig, UserScheduleConfig
from datetime import datetime

ENV = os.getenv("APP_ENV", "prod")
CONFIG_PATH = Path(__file__).parent / "environments" / f"{ENV}.toml"


class ConfigLoader:
    config: AppConfig

    @classmethod
    def load(cls):
        data = toml.loads(CONFIG_PATH.read_text())
        cls.config = AppConfig(**data)

    @classmethod
    def save(cls):
        raw = cls.config.model_dump()
        CONFIG_PATH.write_text(toml.dumps(raw))

    @classmethod
    def add_link(cls,
                 user_id: int,
                 account_id: str,
                 account_name: str,
                 index_name: str = "IMOEX"):
        for user in cls.config.users:
            if user.telegram_id == user_id:
                user.links=UserLinksConfig(
                    broker_account_id=account_id,
                    broker_account_name=account_name,
                    index_name=index_name
                )
        cls.save()

    @classmethod
    def update_schedule(cls,
                 user_id: int,
                 rebalance_frequency: str,
                 last_run: datetime = None):
        if not last_run:
            last_run = datetime.now()
        for user in cls.config.users:
            if user.telegram_id == user_id:
                user.schedule=UserScheduleConfig(
                    last_run=last_run,
                    rebalance_frequency=rebalance_frequency
                )
        cls.save()
