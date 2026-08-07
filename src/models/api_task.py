from datetime import datetime

from src.models.api_base import BaseApiModel


class TaskResponse(BaseApiModel):
    id: str
    # Имена enum'ов (BOND_EVENTS_MONITOR, REBALANCE; WEEKLY, MONTHLY, QUARTERLY).
    type: str
    frequency: str
    params: dict | None = None
    last_checked_date: datetime | None = None


class CreateTaskRequest(BaseApiModel):
    type: str
    frequency: str
    params: dict


class UpdateTaskRequest(BaseApiModel):
    """Что можно поменять у существующей задачи, не пересоздавая её.

    params — только настройки задачи (REBALANCE: min_free_cash); ссылку на
    стратегию или счёт менять нельзя.
    """
    frequency: str | None = None
    params: dict | None = None
