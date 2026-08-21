from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.notification_settings_service import NotificationSettingsService
from src.db.database import get_session
from src.db.repositories.user_repository import UserRepository


def get_notification_settings_service(
    db: AsyncSession = Depends(get_session),
) -> NotificationSettingsService:
    return NotificationSettingsService(user_repo=UserRepository(db))
