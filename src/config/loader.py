import os
from dataclasses import field

import toml
from pathlib import Path
from datetime import datetime
from typing import Any

from src.models.config import AppConfig, UserIndexBindingsConfig, UserScheduleConfig, BrokerAccountConfig


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
    def _update_user_field(cls, user_id: int, field: str, new_data: dict, model_cls: Any):
        """
        Универсальный метод обновления поля пользователя (schedule, index_bindings и т.д.)
        :param user_id: Идентификатор пользователя
        :param field: имя поля (строкой), например "schedule" или "index_bindings"
        :param new_data: данные, которые нужно обновить (dict)
        :param model_cls: класс модели, например UserScheduleConfig
        """
        for user in cls.config.users:
            if user.telegram_id == user_id:
                current = getattr(user, field, None)
                base_data = current.model_dump() if current else {}
                base_data.update({k: v for k, v in new_data.items() if v is not None})
                setattr(user, field, model_cls(**base_data))
        cls.save()

    @classmethod
    def update_broker_account(cls, user_id: int, account_id: str, account_name: str, target: str = "index_bindings"):
        """
        Обновить аккаунт брокера для пользователя
        :param user_id: Идентификатор пользователя.
        :param account_id: Идентификатор аккаунта брокера.
        :param account_name: Название аккаунта брокера.
        :param target: Для какой связки обновляем аккаунт брокера. По умолчанию index_bindings.
        """
        if target == "index_bindings":
            field_for_update = "index_bindings"
            model_for_update = UserIndexBindingsConfig
        elif target == "bonds_account":
            field_for_update = "bonds_account"
            model_for_update = BrokerAccountConfig

        cls._update_user_field(
            user_id=user_id,
            field=field_for_update,
            new_data={"broker_account_id": account_id, "broker_account_name": account_name},
            model_cls=model_for_update
        )

    @classmethod
    def update_tracking_index(cls, user_id: int, index_name: str):
        """
        Обновить индекс Мосбиржи для отслеживания.
        :param user_id: Идентификатор пользователя.
        :param index_name: Индекс Мосбиржи.
        """
        cls._update_user_field(
            user_id=user_id,
            field="index_bindings",
            new_data={"index_name": index_name},
            model_cls=UserIndexBindingsConfig
        )

    @classmethod
    def update_schedule(cls, user_id: int, rebalance_frequency: str, last_run: datetime = None):
        """
        Обновить изменение расписания балансировки портфеля.
        :param user_id: Пользователь, которому меняем настройки
        :param rebalance_frequency: Новая частота балансировки.
        :param last_run: Дата последнего запуска балансировки.
        """
        if not last_run:
            last_run = datetime.now()
        cls._update_user_field(
            user_id=user_id,
            field="schedule",
            new_data={
                "rebalance_frequency": rebalance_frequency,
                "last_run": last_run
            },
            model_cls=UserScheduleConfig
        )

    @classmethod
    def change_bond_reminder_state(cls, user_id: int, is_enabled: bool):
        """
        Изменение состояния напоминания для облигаций, которые требуют отслеживания.
        :param user_id: Идентификатор пользователя, которому меняем конфигурацию.
        :param is_enabled: Флаг включения/выключения, который будет проставлен.
        """
        if is_enabled:
            new_data = {
                "enable_bond_reminder": is_enabled,
                "bond_reminder_last_run": datetime.now()
            }
        else:
            new_data = {
                "enable_bond_reminder": is_enabled
            }
        cls._update_user_field(
            user_id=user_id,
            field="schedule",
            new_data=new_data,
            model_cls=UserScheduleConfig
        )

    @classmethod
    def change_bond_reminder_last_run(cls, user_id: int, last_run: datetime = None):
        """
        Изменение дату последнего запуска проверки облигаций на близость корпоративного действия.
        :param user_id: Идентификатор пользователя, которому меняем конфигурацию.
        :param last_run: Дата последнего запуска проверки облигаций на близость корпоративного действия.
        """
        if not last_run:
            last_run = datetime.now()
        cls._update_user_field(
            user_id=user_id,
            field="schedule",
            new_data={"bond_reminder_last_run": last_run},
            model_cls=UserScheduleConfig
        )
