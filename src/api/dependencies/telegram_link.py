from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.telegram_link_service import TelegramLinkService
from src.db.database import get_session
from src.db.repositories.auth_identity_repository import AuthIdentityRepository
from src.db.repositories.telegram_link_repository import TelegramLinkRepository


def get_telegram_link_service(db: AsyncSession = Depends(get_session)) -> TelegramLinkService:
    return TelegramLinkService(
        identity_repo=AuthIdentityRepository(db),
        link_repo=TelegramLinkRepository(db),
    )
