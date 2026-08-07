import hmac

from fastapi import Header, HTTPException

from src.config import api_settings


def require_service_key(x_service_key: str = Header(default="")) -> None:
    """Авторизация сервисных запросов бота по общему ключу.

    Ключ защищает только /service/telegram/* — дальше бот работает
    обычным пользовательским JWT.
    """
    if not api_settings.BOT_API_KEY:
        raise HTTPException(status_code=503, detail="service_auth_disabled")

    if not hmac.compare_digest(x_service_key, api_settings.BOT_API_KEY):
        raise HTTPException(status_code=401, detail="invalid_service_key")
