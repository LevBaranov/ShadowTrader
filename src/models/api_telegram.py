from datetime import datetime

from src.models.api_base import BaseApiModel
from src.models.notification_channel import NotificationChannel


class TelegramIdRequest(BaseApiModel):
    telegram_id: int


class ServiceTokenResponse(BaseApiModel):
    access_token: str
    token_type: str
    # Секунды до истечения — бот кэширует токен по этому значению.
    expires_in: int


class TelegramRegisterResponse(BaseApiModel):
    user_id: str


class LinkRequestResponse(BaseApiModel):
    code: str
    expires_at: datetime


class TelegramLinkConfirmRequest(BaseApiModel):
    code: str


class TelegramLinkResponse(BaseApiModel):
    telegram_id: int


class UserProfile(BaseApiModel):
    email: str | None
    # Почта, ожидающая подтверждения кодом (начатая смена/добавление почты).
    pending_email: str | None = None
    telegram_linked: bool
    # Куда уходят уведомления планировщика.
    notification_channel: NotificationChannel = NotificationChannel.TELEGRAM


class NotificationChannelRequest(BaseApiModel):
    channel: NotificationChannel
