from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.portfolio_manager import PortfolioManager
from src.db.database import get_session
from src.db.repositories.brokers_account_repository import BrokersAccountRepository
from src.db.repositories.stock_markets_index_repository import StockMarketsIndexRepository
from src.db.repositories.users_strategy_repository import UsersStrategyRepository
from src.core.user_service import UserService
from src.core.strategy_service import StrategyService
from src.services.stock_market import Moex


def get_strategy_service(
    session: AsyncSession = Depends(get_session)
) -> UserService:

    return UserService(UsersStrategyRepository(session), PortfolioManager)


def get_strategy_manager(
    session: AsyncSession = Depends(get_session)
) -> StrategyService:

    return StrategyService(
        strategy_repo=UsersStrategyRepository(session),
        accounts_repo=BrokersAccountRepository(session),
        index_repo=StockMarketsIndexRepository(session),
        stock_market_client_factory=Moex,
    )