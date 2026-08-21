"""Пользовательские задачи планировщика: напоминания по облигациям и автобалансировка.

Соглашение по params:
- BOND_EVENTS_MONITOR: {"brokers_account_id": "<uuid brokers_account.id>"}
- REBALANCE: {"strategy_id": "<uuid users_strategy.id>", "min_free_cash": <int>}

min_free_cash — настройка планировщика: порог свободного кэша, ниже которого
автобалансировка не запускается (раньше был общим для всех в toml —
[balancer].max_cash). Не путать с users_strategy.max_cash: тот про то, сколько
денег балансировщик не тратит на покупки.

Принадлежность сущности из params пользователю проверяется при исполнении задачи
планировщиком (task.user_id против владельца сущности) — здесь валидируем формат
и защищаемся от дублей.
"""
import uuid

from src.db.enums import TaskType
from src.db.models.task import Task
from src.models.scheduler_frequency import ScheduleFrequency

TASK_REQUIRED_PARAM = {
    TaskType.BOND_EVENTS_MONITOR: "brokers_account_id",
    TaskType.REBALANCE: "strategy_id",
}

# Порог по умолчанию для новой задачи автобалансировки: значение прежнего
# общего [balancer].max_cash из prod.toml. Дальше пользователь меняет его сам.
DEFAULT_MIN_FREE_CASH = 2000


class TaskValidationError(Exception):
    """Некорректный тип/частота/params задачи."""


class TaskAlreadyExistsError(Exception):
    """Активная задача с теми же type+params уже существует."""


class TaskNotFoundError(Exception):
    """Задача не найдена у пользователя (или уже отключена)."""


class TaskService:
    def __init__(self, task_repo):
        self.task_repo = task_repo

    async def list_tasks(self, user) -> list[Task]:
        return await self.task_repo.get_user_tasks(user.id)

    async def create_task(self, user, task_type: str, frequency: str, params: dict | None) -> Task:
        try:
            task_type_enum = TaskType[task_type]
        except KeyError:
            raise TaskValidationError(f"Unknown task type: {task_type}")

        try:
            frequency_enum = ScheduleFrequency[frequency]
        except KeyError:
            raise TaskValidationError(f"Unknown frequency: {frequency}")

        param_key = TASK_REQUIRED_PARAM[task_type_enum]
        param_value = (params or {}).get(param_key)
        try:
            uuid.UUID(str(param_value))
        except (ValueError, TypeError):
            raise TaskValidationError(f"params.{param_key} must be a UUID")

        normalized_params = {param_key: str(param_value)}

        # Дубли ищем по ссылке на сущность, поэтому настройки задачи добавляем после.
        existing = await self.task_repo.get_user_tasks(user.id, **normalized_params)
        if any(task.task_type == task_type_enum for task in existing):
            raise TaskAlreadyExistsError(f"{task_type} for {param_value} already active")

        if task_type_enum == TaskType.REBALANCE:
            raw_min_free_cash = (params or {}).get("min_free_cash")
            normalized_params["min_free_cash"] = (
                DEFAULT_MIN_FREE_CASH
                if raw_min_free_cash is None
                else _parse_min_free_cash(raw_min_free_cash)
            )

        return await self.task_repo.create_task(
            task_type=task_type_enum,
            frequency=frequency_enum,
            user=user,
            params=normalized_params,
        )

    async def update_task(
        self, user, task_id: uuid.UUID, frequency: str | None, params: dict | None
    ) -> Task:
        """Поменять расписание и настройки задачи, не пересоздавая её.

        Ссылку на сущность (strategy_id / brokers_account_id) не трогаем: это
        другая задача, её создают заново.
        """
        task = await self._get_own_active_task(user, task_id)

        new_frequency = None
        if frequency is not None:
            try:
                new_frequency = ScheduleFrequency[frequency]
            except KeyError:
                raise TaskValidationError(f"Unknown frequency: {frequency}")

        new_params = None
        if params and "min_free_cash" in params:
            if task.task_type != TaskType.REBALANCE:
                raise TaskValidationError("min_free_cash is only for REBALANCE tasks")

            new_params = dict(task.params or {})
            new_params["min_free_cash"] = _parse_min_free_cash(params["min_free_cash"])

        if new_frequency is None and new_params is None:
            return task

        return await self.task_repo.update_task(
            task_id, frequency=new_frequency, params=new_params
        )

    async def disable_task(self, user, task_id: uuid.UUID) -> None:
        await self._get_own_active_task(user, task_id)

        await self.task_repo.disable_task(task_id)

    async def _get_own_active_task(self, user, task_id: uuid.UUID) -> Task:
        task = await self.task_repo.get_task(task_id)

        if task is None or task.user_id != user.id or task.disabled_date is not None:
            raise TaskNotFoundError(str(task_id))

        return task


def _parse_min_free_cash(value) -> int:
    """Порог должен быть неотрицательным целым: приходит из JSON, где могут быть строки."""
    if isinstance(value, bool):
        raise TaskValidationError("params.min_free_cash must be a non-negative integer")

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise TaskValidationError("params.min_free_cash must be a non-negative integer")

    if parsed < 0:
        raise TaskValidationError("params.min_free_cash must be a non-negative integer")

    return parsed
