import uuid
from datetime import datetime
from sqlalchemy import cast, select, Integer, Boolean
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.enums import TaskType
from src.db.models.task import Task, TaskResult
from src.db.models.user import User
from src.models.scheduler_frequency import ScheduleFrequency


class TaskRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_tasks(self) -> list[Task]:
        stmt = select(Task)
        result = await self.db.scalars(stmt)

        return list(result)

    async def get_task(self, task_id: uuid.UUID) -> Task | None:
        stmt = select(Task).where(Task.id == task_id)
        result = await self.db.scalar(stmt)
        return result


    async def create_task(
            self,
            task_type: TaskType,
            frequency: ScheduleFrequency,
            user: User | None = None,
            params: dict | None = None
    ) -> Task:

        task = Task(
            task_type=task_type,
            frequency=frequency,
            params=params,
            user_id=user.id
        )

        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)

        return task

    async def save_result(self, task_id: uuid.UUID, result: str, errors: str | None = None) -> TaskResult:

        task_result = TaskResult(
            task_id=task_id,
            results=result,
            errors=errors
        )

        self.db.add(task_result)

        task = await self.get_task(task_id)
        if not errors:
            task.last_checked_date = datetime.now()
        task.updated_at = datetime.now()

        await self.db.commit()

        return task_result

    async def get_user_tasks(self, user_telegram_id: int, **params_filters) -> list[Task]:

        stmt = (select(Task).join(User)
                .where(User.telegram_id == user_telegram_id)
                .where(Task.disabled_date.is_(None)))

        for key, value in params_filters.items():
            field = Task.params[key].astext

            if isinstance(value, int):
                stmt = stmt.where(cast(field, Integer) == value)
            elif isinstance(value, bool):
                stmt = stmt.where(cast(field, Boolean) == value)
            else:
                stmt = stmt.where(field == str(value))

        result = await self.db.scalars(stmt)
        return list(result)

    async def disable_task(self, task_id: uuid.UUID) -> Task:

        task = await self.get_task(task_id)
        task.disabled_date = datetime.now()
        task.updated_at = datetime.now()

        await self.db.commit()
        await self.db.refresh(task)

        return task

