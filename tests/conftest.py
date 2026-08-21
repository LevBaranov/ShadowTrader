"""Общая подготовка окружения для тестов.

Настройки должны быть выставлены до первого импорта src.* —
src.config читает окружение при импорте.
"""
import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet

REPO_ROOT = Path(__file__).resolve().parents[1]

# Тесты запускаются из любого каталога.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Тесты не пишут файлы логов.
os.environ.setdefault("LOG_ENABLED", "0")

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test")

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("BOT_API_KEY", "test-bot-api-key")
os.environ.setdefault("JWT_ISSUER", "shadowtrader-tests")
os.environ.setdefault("JWT_AUDIENCE", "shadowtrader-tests")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
