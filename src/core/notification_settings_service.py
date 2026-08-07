"""Настройки уведомлений пользователя.

Раньше канал был зашит в код («Telegram, если привязан, иначе почта») — теперь
это настройка в БД, которой пользователь управляет через API.
"""
import logging

from src.db.models.user import User
from src.models.notification_channel import NotificationChannel

logger = logging.getLogger(__name__)


class NotificationChannelUnavailableError(Exception):
    """У пользователя нет способа входа, который нужен выбранному каналу."""


class NotificationSettingsService:
    def __init__(self, user_repo):
        self.user_repo = user_repo

    async def set_channel(self, user: User, channel: NotificationChannel) -> User:
        """Сменить канал уведомлений.

        Канал без соответствующего способа входа не даём выбрать: настройка,
        которая ничего не делает, хуже явной ошибки. ALL допустим, если доступен
        хотя бы один канал — второй заработает после привязки.
        """
        has_telegram = user.telegram_id is not None
        has_email = bool(user.email)

        if channel == NotificationChannel.TELEGRAM and not has_telegram:
            raise NotificationChannelUnavailableError("telegram_not_linked")
        if channel == NotificationChannel.EMAIL and not has_email:
            raise NotificationChannelUnavailableError("email_not_confirmed")
        if channel == NotificationChannel.ALL and not (has_telegram or has_email):
            raise NotificationChannelUnavailableError("no_channels_available")

        user.notification_channel = channel
        await self.user_repo.save()

        logger.info("Пользователь %s выбрал канал уведомлений %s", user.id, channel.value)

        return user
