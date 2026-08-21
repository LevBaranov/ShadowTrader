from fastapi import APIRouter, HTTPException, Depends

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.strategy import get_strategy_service
from src.core.user_service import UserService, StrategyNotFoundError, AccountDeletedError
from src.models.api_user import RebalanceRequest
from src.models.rebalance import RebalanceResult

router = APIRouter(prefix="/portfolios")


@router.post("/balance", response_model=RebalanceResult)
async def exec_balance(
    body: RebalanceRequest,
    current_user=Depends(get_current_user),
    strategy_service: UserService = Depends(get_strategy_service),
):
    try:
        return await strategy_service.execute_strategy_rebalance(
            current_user, body.strategy_id
        )
    except StrategyNotFoundError:
        raise HTTPException(status_code=404, detail="Strategy not found")
    except AccountDeletedError:
        raise HTTPException(
            status_code=422, detail="Счёт стратегии помечен удалённым у брокера"
        )
