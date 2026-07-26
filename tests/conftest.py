"""Общая подготовка окружения для тестов.

Настройки должны быть выставлены до первого импорта src.* —
src.config читает env и toml при импорте.
"""
import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet

REPO_ROOT = Path(__file__).resolve().parents[1]

# Тесты запускаются из любого каталога.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("APP_ENV", "dev")
os.environ.setdefault("APP_CONFIG_FILE_PATH", f"{REPO_ROOT}/")

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test")

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("JWT_ISSUER", "shadowtrader-tests")
os.environ.setdefault("JWT_AUDIENCE", "shadowtrader-tests")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
