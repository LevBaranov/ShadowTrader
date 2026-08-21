from typing import List

from fastapi import APIRouter, Depends

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.strategy import get_strategy_manager
from src.core.strategy_service import StrategyService
from src.models.api_index import IndexResponse

router = APIRouter(prefix="/indices")


@router.get("", response_model=List[IndexResponse])
async def list_indices(
    current_user=Depends(get_current_user),
    strategy_service: StrategyService = Depends(get_strategy_manager),
):
    """Список индексов бирж из БД (для выбора при создании стратегии)."""
    indices = await strategy_service.list_indices()
    return [
        IndexResponse(
            id=str(index.id),
            stock_market=index.stock_market,
            index_name=index.index_name,
            description=index.description,
        )
        for index in indices
    ]
