"""Логирование бота — тот же подход, что и на бэкенде.

Бот не имеет доступа к коду бэкенда (см. tests/test_no_backend_imports.py),
поэтому модуль самостоятельный, но формат строк и переменные окружения общие:

    LOG_PATH     каталог логов (по умолчанию <корень>/logs, монтируется на хост)
    LOG_ENABLED  писать ли файлы логов (0 — только stdout)
    LOG_VERBOSE  писать запрос/ответ целиком
    LOG_LEVEL    уровень общего лога

Файлы: `bot.log` — общий лог процесса, `api.log` — вызовы бэкенда (единственная
внешняя интеграция бота: с Telegram общается aiogram, её лог идёт в общий).
"""
import json
import logging
import os
import re
import sys
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from time import monotonic

PROJECT_ROOT = Path(__file__).resolve().parents[1]

LOG_FORMAT = "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3

SECRET_MARKERS = ("token", "password", "secret", "key", "authorization")
MASK = "***"
# Секреты встречаются и внутри тел запросов/ответов ("accessToken": "…"),
# где ключом поля лога их не отловить.
SECRET_JSON = re.compile(
    r'("[^"]*(?:%s)[^"]*"\s*:\s*)"[^"]*"' % "|".join(SECRET_MARKERS),
    re.IGNORECASE,
)

SHORT_LIMIT = 120
DETAIL_LIMIT = 4000

NOISY_LOGGERS = ("httpx", "httpcore", "aiohttp", "asyncio")


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _log_dir() -> Path:
    # Относительный путь — от корня проекта, а не от каталога запуска:
    # логи не должны попадать внутрь пакета с кодом.
    path = Path(os.getenv("LOG_PATH") or "logs")
    return path if path.is_absolute() else PROJECT_ROOT / path


LOG_DIR = _log_dir()
ENABLED = _env_flag("LOG_ENABLED", True)
VERBOSE = _env_flag("LOG_VERBOSE", False)
LEVEL = (os.getenv("LOG_LEVEL") or "INFO").upper()

_configured = False


def _file_handler(name: str) -> logging.Handler:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        LOG_DIR / f"{name}.log", maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    return handler


def setup_logging() -> None:
    """Настроить логирование процесса: stdout + `bot.log`. Вызывать один раз на старте."""
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if VERBOSE else LEVEL)

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    root.addHandler(stream)

    if ENABLED:
        root.addHandler(_file_handler("bot"))

    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.DEBUG if VERBOSE else logging.WARNING)


def integration_logger(service: str) -> logging.Logger:
    """Логгер интеграции: пишет в свой файл и, как обычно, в общий лог/stdout."""
    logger = logging.getLogger(f"integration.{service}")
    logger.setLevel(logging.DEBUG if VERBOSE else logging.INFO)

    if ENABLED and not logger.handlers:
        logger.addHandler(_file_handler(service))

    return logger


def _value(value, limit: int) -> str:
    if isinstance(value, (dict, list, tuple)):
        text = json.dumps(value, ensure_ascii=False, default=str)
    else:
        text = str(value)

    text = SECRET_JSON.sub(rf'\1"{MASK}"', text)

    if len(text) > limit:
        text = f"{text[:limit]}…({len(text)})"
    return text


def _fields(fields: dict, limit: int) -> str:
    parts = []
    for key, value in fields.items():
        if any(marker in key.lower() for marker in SECRET_MARKERS):
            value = MASK
        elif value is None:
            continue
        parts.append(f"{key}={_value(value, limit)}")
    return " ".join(parts)


class IntegrationCall:
    """Один вызов внешнего сервиса: копит короткий итог и подробности."""

    def __init__(self, logger: logging.Logger, operation: str, params: dict):
        self._logger = logger
        self._operation = operation
        self._fields = dict(params)
        self._details: dict = {}
        self._started = monotonic()
        self._status = "ok"

    def add(self, **fields) -> None:
        """Короткие поля итога — попадают в основную строку лога."""
        self._fields.update(fields)

    def detail(self, **fields) -> None:
        """Полные запрос/ответ — пишутся только в подробном режиме."""
        if VERBOSE:
            self._details.update(fields)

    def failed(self, reason: str) -> None:
        """Вызов дошёл до сервиса, но ответ неуспешный (например, HTTP 4xx/5xx)."""
        self._status = "error"
        self._fields["reason"] = reason

    def write(self, error: BaseException | None = None) -> None:
        duration_ms = int((monotonic() - self._started) * 1000)
        status = "error" if error is not None else self._status

        fields = dict(self._fields)
        if error is not None:
            fields["error"] = f"{type(error).__name__}: {error}"

        line = f"{self._operation} | {status} | {duration_ms}ms"
        summary = _fields(fields, SHORT_LIMIT)
        if summary:
            line = f"{line} | {summary}"

        self._logger.log(logging.ERROR if status == "error" else logging.INFO, line)

        if self._details:
            self._logger.debug("%s | detail | %s", self._operation, _fields(self._details, DETAIL_LIMIT))


@contextmanager
def integration_call(service: str, operation: str, **params):
    """Обернуть вызов внешнего сервиса одной строкой лога."""
    call = IntegrationCall(integration_logger(service), operation, params)
    try:
        yield call
    except Exception as error:
        call.write(error)
        raise
    else:
        call.write()
