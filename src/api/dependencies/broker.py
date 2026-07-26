from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.broker_service import BrokerService
from src.db.database import get_session
from src.db.repositories.brokers_account_repository import BrokersAccountRepository
from src.db.repositories.users_broker_repository import UsersBrokerRepository
from src.db.repositories.users_strategy_repository import UsersStrategyRepository
from src.services.broker import TBroker


def get_broker_service(
    session: AsyncSession = Depends(get_session),
) -> BrokerService:
    return BrokerService(
        broker_repo=UsersBrokerRepository(session),
        accounts_repo=BrokersAccountRepository(session),
        broker_client_factory=TBroker,
        strategy_repo=UsersStrategyRepository(session),
    )
