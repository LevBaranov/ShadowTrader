"""Тесты TaskService (fake-репозиторий задач)."""
import asyncio
import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest

from src.db.enums import TaskType
from src.models.scheduler_frequency import ScheduleFrequency
from src.core.task_service import (
    DEFAULT_MIN_FREE_CASH,
    TaskService,
    TaskValidationError,
    TaskAlreadyExistsError,
    TaskNotFoundError,
)


class FakeTaskRepo:
    def __init__(self):
        self.tasks = []

    async def get_user_tasks(self, user_id, **params_filters):
        result = []
        for task in self.tasks:
            if task.user_id != user_id or task.disabled_date is not None:
                continue
            params = task.params or {}
            if all(str(params.get(k)) == str(v) for k, v in params_filters.items()):
                result.append(task)
        return result

    async def get_task(self, task_id):
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    async def create_task(self, task_type, frequency, user=None, params=None):
        task = SimpleNamespace(
            id=uuid.uuid4(),
            task_type=task_type,
            frequency=frequency,
            user_id=user.id,
            params=params,
            last_checked_date=datetime.now(),
            disabled_date=None,
        )
        self.tasks.append(task)
        return task

    async def update_task(self, task_id, frequency=None, params=None):
        task = await self.get_task(task_id)
        if frequency is not None:
            task.frequency = frequency
        if params is not None:
            task.params = params
        return task

    async def disable_task(self, task_id):
        task = await self.get_task(task_id)
        task.disabled_date = datetime.now()
        return task


@pytest.fixture
def repo():
    return FakeTaskRepo()


@pytest.fixture
def service(repo):
    return TaskService(task_repo=repo)


@pytest.fixture
def user():
    return SimpleNamespace(id=uuid.uuid4())


def test_create_rebalance_task(service, user):
    strategy_id = str(uuid.uuid4())

    task = asyncio.run(service.create_task(
        user, "REBALANCE", "WEEKLY", {"strategy_id": strategy_id}
    ))

    assert task.task_type == TaskType.REBALANCE
    assert task.frequency == ScheduleFrequency.WEEKLY
    # Порог автобалансировки всегда лежит в params явно — дальше его правит пользователь.
    assert task.params == {
        "strategy_id": strategy_id,
        "min_free_cash": DEFAULT_MIN_FREE_CASH,
    }


def test_create_rebalance_task_with_min_free_cash(service, user):
    strategy_id = str(uuid.uuid4())

    task = asyncio.run(service.create_task(
        user, "REBALANCE", "WEEKLY", {"strategy_id": strategy_id, "min_free_cash": 5000}
    ))

    assert task.params["min_free_cash"] == 5000


def test_create_rebalance_task_accepts_zero_threshold(service, user):
    task = asyncio.run(service.create_task(
        user, "REBALANCE", "WEEKLY",
        {"strategy_id": str(uuid.uuid4()), "min_free_cash": 0},
    ))

    assert task.params["min_free_cash"] == 0


@pytest.mark.parametrize("value", [-1, "много", True])
def test_create_rebalance_task_invalid_min_free_cash(service, user, value):
    with pytest.raises(TaskValidationError):
        asyncio.run(service.create_task(
            user, "REBALANCE", "WEEKLY",
            {"strategy_id": str(uuid.uuid4()), "min_free_cash": value},
        ))


def test_create_rebalance_task_null_threshold_falls_back_to_default(service, user):
    """Явный null трактуем как «не задано» — берём дефолт, а не 0."""
    task = asyncio.run(service.create_task(
        user, "REBALANCE", "WEEKLY",
        {"strategy_id": str(uuid.uuid4()), "min_free_cash": None},
    ))

    assert task.params["min_free_cash"] == DEFAULT_MIN_FREE_CASH


def test_bond_monitor_task_has_no_threshold(service, user):
    task = asyncio.run(service.create_task(
        user, "BOND_EVENTS_MONITOR", "WEEKLY", {"brokers_account_id": str(uuid.uuid4())}
    ))

    assert "min_free_cash" not in task.params


class TestUpdateTask:

    def test_changes_frequency_and_threshold(self, service, user):
        strategy_id = str(uuid.uuid4())
        task = asyncio.run(service.create_task(
            user, "REBALANCE", "WEEKLY", {"strategy_id": strategy_id}
        ))

        updated = asyncio.run(service.update_task(
            user, task.id, "MONTHLY", {"min_free_cash": 100}
        ))

        assert updated.frequency == ScheduleFrequency.MONTHLY
        assert updated.params == {"strategy_id": strategy_id, "min_free_cash": 100}

    def test_keeps_entity_reference(self, service, user):
        """Ссылку на стратегию через params подменить нельзя."""
        strategy_id = str(uuid.uuid4())
        task = asyncio.run(service.create_task(
            user, "REBALANCE", "WEEKLY", {"strategy_id": strategy_id}
        ))

        updated = asyncio.run(service.update_task(
            user, task.id, None, {"strategy_id": str(uuid.uuid4()), "min_free_cash": 1}
        ))

        assert updated.params["strategy_id"] == strategy_id

    def test_empty_body_is_noop(self, service, user):
        task = asyncio.run(service.create_task(
            user, "REBALANCE", "WEEKLY", {"strategy_id": str(uuid.uuid4())}
        ))

        updated = asyncio.run(service.update_task(user, task.id, None, None))

        assert updated.frequency == ScheduleFrequency.WEEKLY

    def test_unknown_frequency_raises(self, service, user):
        task = asyncio.run(service.create_task(
            user, "REBALANCE", "WEEKLY", {"strategy_id": str(uuid.uuid4())}
        ))

        with pytest.raises(TaskValidationError):
            asyncio.run(service.update_task(user, task.id, "HOURLY", None))

    def test_threshold_only_for_rebalance(self, service, user):
        task = asyncio.run(service.create_task(
            user, "BOND_EVENTS_MONITOR", "WEEKLY", {"brokers_account_id": str(uuid.uuid4())}
        ))

        with pytest.raises(TaskValidationError):
            asyncio.run(service.update_task(user, task.id, None, {"min_free_cash": 10}))

    def test_foreign_task_raises(self, service, user):
        other_user = SimpleNamespace(id=uuid.uuid4())
        task = asyncio.run(service.create_task(
            other_user, "REBALANCE", "WEEKLY", {"strategy_id": str(uuid.uuid4())}
        ))

        with pytest.raises(TaskNotFoundError):
            asyncio.run(service.update_task(user, task.id, "MONTHLY", None))


def test_create_bond_monitor_task(service, user):
    account_id = str(uuid.uuid4())

    task = asyncio.run(service.create_task(
        user, "BOND_EVENTS_MONITOR", "WEEKLY", {"brokers_account_id": account_id}
    ))

    assert task.task_type == TaskType.BOND_EVENTS_MONITOR


def test_unknown_type_raises(service, user):
    with pytest.raises(TaskValidationError):
        asyncio.run(service.create_task(user, "NOPE", "WEEKLY", {"strategy_id": str(uuid.uuid4())}))


def test_unknown_frequency_raises(service, user):
    with pytest.raises(TaskValidationError):
        asyncio.run(service.create_task(user, "REBALANCE", "HOURLY", {"strategy_id": str(uuid.uuid4())}))


def test_missing_param_raises(service, user):
    with pytest.raises(TaskValidationError):
        asyncio.run(service.create_task(user, "REBALANCE", "WEEKLY", {}))


def test_invalid_uuid_param_raises(service, user):
    with pytest.raises(TaskValidationError):
        asyncio.run(service.create_task(user, "REBALANCE", "WEEKLY", {"strategy_id": "not-a-uuid"}))


def test_duplicate_active_task_raises(service, user):
    strategy_id = str(uuid.uuid4())
    asyncio.run(service.create_task(user, "REBALANCE", "WEEKLY", {"strategy_id": strategy_id}))

    with pytest.raises(TaskAlreadyExistsError):
        asyncio.run(service.create_task(user, "REBALANCE", "MONTHLY", {"strategy_id": strategy_id}))


def test_recreate_after_disable(service, repo, user):
    strategy_id = str(uuid.uuid4())
    task = asyncio.run(service.create_task(user, "REBALANCE", "WEEKLY", {"strategy_id": strategy_id}))
    asyncio.run(service.disable_task(user, task.id))

    asyncio.run(service.create_task(user, "REBALANCE", "MONTHLY", {"strategy_id": strategy_id}))

    assert len(asyncio.run(service.list_tasks(user))) == 1


def test_disable_foreign_task_raises(service, repo, user):
    other_user = SimpleNamespace(id=uuid.uuid4())
    task = asyncio.run(service.create_task(
        other_user, "REBALANCE", "WEEKLY", {"strategy_id": str(uuid.uuid4())}
    ))

    with pytest.raises(TaskNotFoundError):
        asyncio.run(service.disable_task(user, task.id))


def test_disable_unknown_task_raises(service, user):
    with pytest.raises(TaskNotFoundError):
        asyncio.run(service.disable_task(user, uuid.uuid4()))


def test_list_returns_only_active(service, user):
    task = asyncio.run(service.create_task(
        user, "REBALANCE", "WEEKLY", {"strategy_id": str(uuid.uuid4())}
    ))
    asyncio.run(service.create_task(
        user, "BOND_EVENTS_MONITOR", "WEEKLY", {"brokers_account_id": str(uuid.uuid4())}
    ))
    asyncio.run(service.disable_task(user, task.id))

    tasks = asyncio.run(service.list_tasks(user))

    assert len(tasks) == 1
    assert tasks[0].task_type == TaskType.BOND_EVENTS_MONITOR
