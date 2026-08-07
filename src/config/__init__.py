"""Настройки приложения — только из окружения."""
from .settings import (
    APISettings,
    DBSettings,
    EmailSettings,
    NotificationSettings,
    SchedulerSettings,
    StockMarketSettings,
)

db_settings = DBSettings()
api_settings = APISettings()
email_settings = EmailSettings()
notification_settings = NotificationSettings()
scheduler_settings = SchedulerSettings()
stock_market_settings = StockMarketSettings()
