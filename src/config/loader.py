import os
import toml
from pathlib import Path
from datetime import datetime

from src.models.config import AppConfig, UserIndexBindingsConfig, UserScheduleConfig


ENV = os.getenv("APP_ENV", "prod")
CONFIG_FILE_PATH = os.getenv("APP_CONFIG_FILE_PATH", "/")
config_file = Path(f"{CONFIG_FILE_PATH}{ENV}.toml")


class ConfigLoader:
    config: AppConfig

    @classmethod
    def load(cls):
        data = toml.loads(config_file.read_text())
        cls.config = AppConfig(**data)

    @classmethod
    def save(cls):
        raw = cls.config.model_dump()
        config_file.write_text(toml.dumps(raw))

    @classmethod
    def update_broker_account(
            cls,
            user_id: int,
            account_id: str,
            account_name: str):

        for user in cls.config.users:
            if user.telegram_id == user_id:
                if user.index_bindings:
                    user.index_bindings=UserIndexBindingsConfig(
                        broker_account_id=account_id,
                        broker_account_name=account_name,
                        index_name=user.index_bindings.index_name
                    )
                else:
                    user.index_bindings = UserIndexBindingsConfig(
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
                if user.index_bindings:
                    user.index_bindings = UserIndexBindingsConfig(
                        broker_account_id=user.index_bindings.broker_account_id,
                        broker_account_name=user.index_bindings.broker_account_name,
                        index_name=index_name
                    )
                else:
                    user.index_bindings = UserIndexBindingsConfig(
                        index_name=index_name
                    )

        cls.save()
