from fastapi import APIRouter, Depends

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.strategy import get_strategy_service
from src.core.user_service import UserService
from src.models.api_user import CurrentUserInfo

router = APIRouter(prefix="/users")


@router.get("/me", response_model=CurrentUserInfo)
async def get_me(
        current_user=Depends(get_current_user),
        strategy_service: UserService = Depends(get_strategy_service)
):

    user_strategies = await strategy_service.get_user_strategies(current_user)


    return CurrentUserInfo(
        id=str(current_user.id),
        email=current_user.email,
        strategies=user_strategies
    )



