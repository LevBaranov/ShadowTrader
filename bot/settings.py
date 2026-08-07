import os

from pydantic_settings import BaseSettings


class BotSettings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN")
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://api:8000")
    # Сервисный ключ для /service/telegram/* — тот же, что у бэкенда.
    BOT_API_KEY: str = os.getenv("BOT_API_KEY")
    # База веб-приложения для диплинка привязки: {WEB_APP_URL}/link-telegram?code=…
    WEB_APP_URL: str = os.getenv("WEB_APP_URL", "")
    # Прокси до Telegram API (напр. socks5://127.0.0.1:1080), если прямой доступ закрыт.
    TELEGRAM_PROXY: str | None = os.getenv("TELEGRAM_PROXY") or None
