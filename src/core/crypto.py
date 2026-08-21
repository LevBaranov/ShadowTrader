"""Шифрование секретов (брокерских токенов) перед сохранением в БД.

Используем симметричное аутентифицированное шифрование Fernet (AES-128-CBC + HMAC).
Ключ берётся из настроек (`TOKEN_ENCRYPTION_KEY`) и не пересекается с JWT `SECRET_KEY`,
чтобы ротация одного не ломала другое.
"""
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from src.config import api_settings


class TokenCryptoError(Exception):
    """Ошибка шифрования/расшифровки брокерского токена."""


@lru_cache(maxsize=1)
def _get_cipher() -> Fernet:
    key = api_settings.TOKEN_ENCRYPTION_KEY
    if not key:
        raise TokenCryptoError(
            "TOKEN_ENCRYPTION_KEY не задан — невозможно шифровать/расшифровывать токены брокера"
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        raise TokenCryptoError("TOKEN_ENCRYPTION_KEY имеет неверный формат (ожидается Fernet-ключ)") from exc


def encrypt_token(plaintext: str) -> str:
    """Зашифровать токен для хранения в БД. Возвращает строку-шифротекст."""
    if not plaintext:
        raise TokenCryptoError("Пустой токен нельзя зашифровать")
    return _get_cipher().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Расшифровать токен, извлечённый из БД, перед использованием."""
    try:
        return _get_cipher().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise TokenCryptoError("Не удалось расшифровать брокерский токен (неверный ключ или повреждённые данные)") from exc
