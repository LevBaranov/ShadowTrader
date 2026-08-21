from enum import Enum


class NotificationChannel(str, Enum):
    """Куда пользователь хочет получать уведомления планировщика.

    Значения совпадают с именами: enum ходит и в БД (users.notification_channel),
    и наружу в контракте API как есть.

    Канал реально доступен только при соответствующем способе входа: TELEGRAM —
    привязанный telegram_id, EMAIL — подтверждённая почта. Если выбранный канал
    недоступен, NotificationService падает на доступный (см. services/notifications.py).
    """
    TELEGRAM = "TELEGRAM"
    EMAIL = "EMAIL"
    ALL = "ALL"
