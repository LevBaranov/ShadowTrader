import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.strategy import get_strategy_manager, get_strategy_service
from src.core.strategy_service import (
    StrategyService,
    StrategyValidationError,
    StrategyNotFoundError,
)
from src.core.user_service import (
    UserService,
    StrategyNotFoundError as UserStrategyNotFoundError,
    AccountDeletedError,
)
from src.models.api_strategy import (
    CreateStrategyRequest,
    StrategyResponse,
    UpdateStrategyRequest,
)
from src.models.api_user import StrategyListItem
from src.models.rebalance import RebalancePreviewResponse

router = APIRouter(prefix="/strategies")


def _to_response(strategy) -> StrategyResponse:
    return StrategyResponse(
        id=str(strategy.id),
        brokers_account_id=str(strategy.brokers_account_id),
        stock_markets_index_id=str(strategy.stock_markets_index_id),
        strategy_type=strategy.strategy_type,
        max_cash=strategy.max_cash,
        delta=strategy.delta,
        min_lots_to_keep=strategy.min_lots_to_keep,
    )


@router.get("", response_model=list[StrategyListItem])
async def list_strategies(
    current_user=Depends(get_current_user),
    user_service: UserService = Depends(get_strategy_service),
) -> list[StrategyListItem]:
    """Лёгкий список стратегий без похода к брокеру (для меню бота)."""
    return await user_service.list_strategies(current_user)


@router.get("/{strategy_id}/rebalance", response_model=RebalancePreviewResponse)
async def get_rebalance_preview(
    strategy_id: uuid.UUID,
    current_user=Depends(get_current_user),
    user_service: UserService = Depends(get_strategy_service),
) -> RebalancePreviewResponse:
    """Превью балансировки: план действий без исполнения."""
    try:
        return await user_service.calculate_strategy_rebalance(current_user, strategy_id)
    except UserStrategyNotFoundError:
        raise HTTPException(status_code=404, detail="strategy_not_found")
    except AccountDeletedError:
        raise HTTPException(status_code=409, detail="account_deleted")


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
            max_cash=body.max_cash,
            delta=body.delta,
            min_lots_to_keep=body.min_lots_to_keep,
        )
    except StrategyValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError:
        # Некорректный UUID аккаунта/индекса в теле запроса.
        raise HTTPException(status_code=422, detail="Invalid account or index id")

    return _to_response(strategy)


@router.patch("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: uuid.UUID,
    body: UpdateStrategyRequest,
    current_user=Depends(get_current_user),
    strategy_service: StrategyService = Depends(get_strategy_manager),
) -> StrategyResponse:
    """Настройки расчёта по стратегии. Комиссия — у брокера, см. PATCH /brokers/{id}."""
    try:
        strategy = await strategy_service.update_settings(
            current_user,
            strategy_id,
            max_cash=body.max_cash,
            delta=body.delta,
            min_lots_to_keep=body.min_lots_to_keep,
        )
    except StrategyNotFoundError:
        raise HTTPException(status_code=404, detail="Strategy not found")
    except StrategyValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return _to_response(strategy)


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
