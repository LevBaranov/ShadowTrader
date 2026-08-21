from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.bond_service import BondService
from src.core.portfolio_manager import PortfolioManager
from src.db.database import get_session
from src.db.repositories.brokers_account_repository import BrokersAccountRepository


def get_bond_service(db: AsyncSession = Depends(get_session)) -> BondService:
    return BondService(
        accounts_repo=BrokersAccountRepository(db),
        portfolio_manager_factory=PortfolioManager,
    )
