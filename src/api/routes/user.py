from fastapi import APIRouter, Depends

from src.api.dependencies.auth import get_current_user
from src.api.utils import get_user_strategies
from src.core.portfolio_manager import PortfolioManager
from src.models.api_user import CurrentUserInfo, BrokerInfoStrategy, UserStrategy, BaseInfo

router = APIRouter(prefix="/users")


@router.get("/me", response_model=CurrentUserInfo)
async def get_me(current_user=Depends(get_current_user)):

    strategies = [ get_user_strategies(current_user) ]
    user_strategies = []
    for _strategy in strategies:

        portfolio_manager = PortfolioManager(_strategy.broker_account_id)

        rebalance = portfolio_manager.calculate_rebalance(_strategy.index_name)

        user_strategies.append(
            UserStrategy(
                broker_info=BrokerInfoStrategy(
                    id="0",
                    name="T-Bank",
                    account=BaseInfo(
                        id=str(_strategy.broker_account_id),
                        name=_strategy.broker_account_name
                    )
                ),
                index_info=BaseInfo(
                    id="0",
                    name=_strategy.index_name
                ),
                portfolio=rebalance.positions,
                free_cash=rebalance.free_cash
            )
        )

    return CurrentUserInfo(
        id=str(current_user.id),
        email=current_user.email,
        strategies=user_strategies
    )



