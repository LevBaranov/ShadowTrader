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

    # Режим запуска бота: "polling" (по умолчанию) или "webhook".
    BOT_RUN_MODE: str = os.getenv("BOT_RUN_MODE", "polling")
    # Публичный URL webhook, на который Telegram шлёт апдейты. Обязателен при BOT_RUN_MODE=webhook.
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
    # Локальные настройки HTTP-сервера, который слушает апдейты бота.
    WEBHOOK_HOST: str = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    WEBHOOK_PORT: int = int(os.getenv("WEBHOOK_PORT", "8080"))
    WEBHOOK_PATH: str = os.getenv("WEBHOOK_PATH", "/webhook")
    # Секретный токен вебхука для защиты endpoint (проверяется заголовком X-Telegram-Bot-Api-Secret-Token).
    WEBHOOK_SECRET_TOKEN: str | None = os.getenv("WEBHOOK_SECRET_TOKEN") or None
