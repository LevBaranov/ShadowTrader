"""Тесты бота запускаются без окружения бэкенда — нужен только корень репозитория
в sys.path, чтобы работал `import bot`.
"""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Тесты не пишут файлы логов.
os.environ.setdefault("LOG_ENABLED", "0")
