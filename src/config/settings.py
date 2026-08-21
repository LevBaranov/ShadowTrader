import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class DBSettings(BaseSettings):
    DB_USER: str = os.getenv("DB_USER")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD")
    DB_HOST: str = os.getenv("DB_HOST")
    DB_PORT: int = os.getenv("DB_PORT")
    DB_NAME: str = os.getenv("DB_NAME")

    def get_db_url(self):
        return (f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@"
                f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}")

class APISettings(BaseSettings):
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    # Сервисный ключ бота: защищает только /service/telegram/*.
    # Не задан — сервисные эндпоинты отвечают 503.
    BOT_API_KEY: str | None = os.getenv("BOT_API_KEY")
    # TTL токенов, выдаваемых по сервисному ключу (короче обычных).
    SERVICE_TOKEN_EXPIRE_MINUTES: int = 15

    JWT_ISSUER: str = os.getenv("JWT_ISSUER")
    JWT_AUDIENCE: str = os.getenv("JWT_AUDIENCE")

    # Ключ (Fernet, url-safe base64, 32 байта) для шифрования брокерских токенов в БД.
    # Держим отдельно от SECRET_KEY, чтобы ротация JWT-секрета не ломала расшифровку токенов.
    # Сгенерировать: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    TOKEN_ENCRYPTION_KEY: str = os.getenv("TOKEN_ENCRYPTION_KEY")


class NotificationSettings(BaseSettings):
    # Токен бота для отправки уведомлений (обычный HTTPS-вызов Telegram Bot API,
    # поллинг-процесс бота для этого не нужен). Не задан — канал Telegram выключен.
    TELEGRAM_BOT_TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN")


class SchedulerSettings(BaseSettings):
    SCHEDULER_INTERVAL_SEC: int = int(os.getenv("SCHEDULER_INTERVAL_SEC", "300"))


class StockMarketSettings(BaseSettings):
    # Точка входа в ISS Мосбиржи и размер страницы при выгрузке состава индекса.
    MOEX_BASE_URL: str = os.getenv("MOEX_BASE_URL", "https://iss.moex.com/iss")
    MOEX_INDEX_LIMIT: int = int(os.getenv("MOEX_INDEX_LIMIT", "100"))


class EmailSettings(BaseSettings):
    # Настройки опциональны: без SMTP_HOST письма не отправляются,
    # а пишутся в лог (удобно для локальной разработки).
    SMTP_HOST: str | None = os.getenv("SMTP_HOST")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str | None = os.getenv("SMTP_USER")
    SMTP_PASSWORD: str | None = os.getenv("SMTP_PASSWORD")
    # Адрес отправителя; по умолчанию совпадает с SMTP_USER.
    EMAIL_FROM: str | None = os.getenv("EMAIL_FROM") or os.getenv("SMTP_USER")

