import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.task import get_task_service
from src.core.task_service import (
    TaskService,
    TaskValidationError,
    TaskAlreadyExistsError,
    TaskNotFoundError,
)
from src.db.models.task import Task
from src.models.api_task import TaskResponse, CreateTaskRequest, UpdateTaskRequest

router = APIRouter(prefix="/tasks")


def _to_response(task: Task) -> TaskResponse:
    return TaskResponse(
        id=str(task.id),
        type=task.task_type.name,
        frequency=task.frequency.name,
        params=task.params,
        last_checked_date=task.last_checked_date,
    )


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    current_user=Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
) -> list[TaskResponse]:
    tasks = await task_service.list_tasks(current_user)
    return [_to_response(task) for task in tasks]


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: CreateTaskRequest,
    current_user=Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    try:
        task = await task_service.create_task(
            current_user, body.type, body.frequency, body.params
        )
    except TaskValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except TaskAlreadyExistsError:
        raise HTTPException(status_code=409, detail="task_already_exists")

    return _to_response(task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID,
    body: UpdateTaskRequest,
    current_user=Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    """Расписание и настройки задачи (REBALANCE: params.min_free_cash)."""
    try:
        task = await task_service.update_task(
            current_user, task_id, body.frequency, body.params
        )
    except TaskValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail="task_not_found")

    return _to_response(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disable_task(
    task_id: uuid.UUID,
    current_user=Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
) -> None:
    try:
        await task_service.disable_task(current_user, task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail="task_not_found")
