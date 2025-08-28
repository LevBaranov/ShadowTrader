import os
import toml
from pathlib import Path
from datetime import datetime

from src.models import AppConfig, UserLinksConfig, UserScheduleConfig


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
    def update_broker_account(
            cls,
            user_id: int,
            account_id: str,
            account_name: str):

        for user in cls.config.users:
            if user.telegram_id == user_id:
                if user.links:
                    user.links=UserLinksConfig(
                        broker_account_id=account_id,
                        broker_account_name=account_name,
                        index_name=user.links.index_name
                    )
                else:
                    user.links = UserLinksConfig(
                        broker_account_id=account_id,
                        broker_account_name=account_name
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

    @classmethod
    def update_tracking_index(cls,
                              user_id: int,
                              index_name: str):
        for user in cls.config.users:
            if user.telegram_id == user_id:
                if user.links:
                    user.links = UserLinksConfig(
                        broker_account_id=user.links.broker_account_id,
                        broker_account_name=user.links.broker_account_name,
                        index_name=index_name
                    )
                else:
                    user.links = UserLinksConfig(
                        index_name=index_name
                    )

        cls.save()
