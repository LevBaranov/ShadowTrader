import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.strategy import get_strategy_manager
from src.core.strategy_service import (
    StrategyService,
    StrategyValidationError,
    StrategyNotFoundError,
)
from src.models.api_strategy import CreateStrategyRequest, StrategyResponse

router = APIRouter(prefix="/strategies")


@router.post("", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
async def create_strategy(
    body: CreateStrategyRequest,
    current_user=Depends(get_current_user),
    strategy_service: StrategyService = Depends(get_strategy_manager),
):
    try:
        strategy = await strategy_service.create_strategy(
            user=current_user,
            brokers_account_id=uuid.UUID(body.brokers_account_id),
            stock_markets_index_id=uuid.UUID(body.stock_markets_index_id),
            strategy_type=body.strategy_type,
        )
    except StrategyValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError:
        # Некорректный UUID аккаунта/индекса в теле запроса.
        raise HTTPException(status_code=422, detail="Invalid account or index id")

    return StrategyResponse(
        id=str(strategy.id),
        brokers_account_id=str(strategy.brokers_account_id),
        stock_markets_index_id=str(strategy.stock_markets_index_id),
        strategy_type=strategy.strategy_type,
    )


@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(
    strategy_id: uuid.UUID,
    current_user=Depends(get_current_user),
    strategy_service: StrategyService = Depends(get_strategy_manager),
):
    try:
        await strategy_service.delete_strategy(current_user, strategy_id)
    except StrategyNotFoundError:
        raise HTTPException(status_code=404, detail="Strategy not found")
