import uuid
from datetime import datetime

from sqlalchemy import func, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base
from src.db.enums import TaskType
from src.models.scheduler_frequency import ScheduleFrequency

class Task(Base):

    __tablename__ = 'task'

    task_type: Mapped[TaskType]
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'))
    params: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    frequency: Mapped[ScheduleFrequency]
    last_checked_date: Mapped[datetime] = mapped_column(server_default=func.now())
    disabled_date: Mapped[datetime | None] = mapped_column()

    user: Mapped["User"] = relationship(
        "User",
        back_populates="tasks",
        lazy="selectin"
    )

    task_results: Mapped[list["TaskResult"]] = relationship(
        "TaskResult",
        back_populates="task",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

class TaskResult(Base):

    __tablename__ = 'task_result'

    results: Mapped[str]
    errors: Mapped[str | None]
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('task.id'))

    task: Mapped["Task"] = relationship(
        "Task",
        back_populates="task_results"
    )
