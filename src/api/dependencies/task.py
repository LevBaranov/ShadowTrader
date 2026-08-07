from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.task_service import TaskService
from src.db.database import get_session
from src.db.repositories.task_repository import TaskRepository


def get_task_service(db: AsyncSession = Depends(get_session)) -> TaskService:
    return TaskService(task_repo=TaskRepository(db))
