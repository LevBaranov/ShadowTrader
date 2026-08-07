"""Уведомления пользователям.

Канал выбирает пользователь (users.notification_channel: TELEGRAM, EMAIL, ALL).
Реально доступен канал только при соответствующем способе входа: Telegram — если
привязан (chat_id = external_id TELEGRAM-identity), почта — если подтверждена.
Если выбранный канал недоступен, падаем на доступный, чтобы уведомление не
потерялось. Ошибка отправки логируется и не пробрасывается — уведомление не
должно ронять задачу.
"""
import logging

import httpx

from src.config import notification_settings
from src.logging_setup import integration_call
from src.models.notification_channel import NotificationChannel
from src.services.email import EmailService, EmailSendError

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org"

# Имя интеграции в логах: пишется в logs/telegram.log.
SERVICE = "telegram"


class TelegramChannel:
    """Отправка в Telegram обычным HTTPS-вызовом Bot API (без aiogram-поллинга)."""

    def __init__(self, bot_token: str | None = None, client: httpx.AsyncClient | None = None):
        self.bot_token = bot_token or notification_settings.TELEGRAM_BOT_TOKEN
        self._client = client or httpx.AsyncClient(base_url=TELEGRAM_API_URL, timeout=30.0)

    async def send(self, chat_id: int, text: str) -> None:
        with integration_call(SERVICE, "send_message", chat_id=chat_id, chars=len(text)) as call:
            if not self.bot_token:
                call.skipped("bot_token_not_configured")
                return

            response = await self._client.post(
                f"/bot{self.bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )

            call.add(status=response.status_code)
            call.detail(text=text, response=response.text)

            response.raise_for_status()


class EmailChannel:
    def __init__(self, email_service: EmailService | None = None):
        self.email_service = email_service or EmailService()

    async def send(self, to: str, subject: str, body: str) -> None:
        await self.email_service.send(to=to, subject=subject, body=body)


class NotificationService:

    def __init__(self, telegram: TelegramChannel | None = None, email: EmailChannel | None = None):
        self.telegram = telegram or TelegramChannel()
        self.email = email or EmailChannel()

    async def notify(self, user, subject: str, text: str) -> None:
        """Уведомить пользователя по выбранным им каналам."""
        for channel in self._channels_for(user):
            try:
                if channel == NotificationChannel.TELEGRAM:
                    await self.telegram.send(user.telegram_id, text)
                else:
                    await self.email.send(user.email, subject, text)
            except (httpx.HTTPError, EmailSendError) as error:
                logger.error(
                    "Не удалось уведомить пользователя %s через %s: %s",
                    user.id, channel.value, error,
                )

    @staticmethod
    def _channels_for(user) -> list[NotificationChannel]:
        """Каналы к отправке: выбранные пользователем и доступные ему.

        Если выбранный канал недоступен (нет привязки или почты) — берём любой
        доступный, чтобы уведомление всё-таки дошло.
        """
        available = []
        if user.telegram_id is not None:
            available.append(NotificationChannel.TELEGRAM)
        if user.email:
            available.append(NotificationChannel.EMAIL)

        if not available:
            logger.warning("У пользователя %s нет каналов для уведомления", user.id)
            return []

        preferred = getattr(user, "notification_channel", None) or NotificationChannel.TELEGRAM
        if preferred == NotificationChannel.ALL:
            return available

        if preferred in available:
            return [preferred]

        logger.info(
            "Канал %s недоступен пользователю %s — уведомляем через %s",
            preferred.value, user.id, available[0].value,
        )
        return [available[0]]
