from fastapi import APIRouter, HTTPException, Depends

from src.api.dependencies.auth import get_current_user
from src.api.utils import get_user_strategies
from src.core.portfolio_manager import PortfolioManager
from src.models.rebalance import RebalanceResult

router = APIRouter(prefix="/portfolios")


@router.post("/balance", response_model=RebalanceResult)
async def exec_balance(current_user=Depends(get_current_user)):

    strategies = [ get_user_strategies(current_user) ]
    for _strategy in strategies:

        portfolio_manager = PortfolioManager(_strategy.broker_account_id)

        rebalance = portfolio_manager.calculate_rebalance(_strategy.index_name)

        success_action_list, error_action_list = portfolio_manager.execute_actions()

    return RebalanceResult(
        success=success_action_list,
        errors=error_action_list,
    )


