from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import get_session
from src.db.repositories.user_repository import UserRepository
from src.db.repositories.task_repository import TaskRepository
from src.api.security import (
    verify_password,
    create_access_token,
)
from src.models.api_user import LoginSuccess, LoginRequest

router = APIRouter(prefix="/auth")


@router.post("/login", response_model=LoginSuccess)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_session)) -> LoginSuccess:
    user_repo = UserRepository(db)
    user = await user_repo.get_user_by_email(data.email)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(str(user.id))

    return LoginSuccess(
        access_token=token,
        token_type="bearer"
    )