"""Единое логирование бэкенда: общий лог процесса и лог интеграций.

Каталог логов НЕ находится внутри пакетов с кодом: относительный путь считается
от корня проекта (а не от текущего каталога процесса), поэтому `logs/` больше не
появляется в `src/api/`, `src/services/` или там, откуда запустили pytest.
В докере каталог монтируется на хост, см. docker-compose.

Файлы в каталоге логов:

* `app.log` — общий лог процесса (то же, что уходит в stdout);
* `broker.log`, `moex.log`, `email.log`, `telegram.log` — по файлу на интеграцию.

Каждый вызов внешнего сервиса — одна строка: что вызвали, чем закончилось,
сколько заняло и минимум параметров:

    2026-08-03 12:00:01 | INFO  | integration.broker | create_order | ok | 118ms | account=2000000001 ticker=SBER type=BUY quantity=2

Ошибка пишется той же строкой со `status=error` и текстом ошибки. Подробности
(полные запрос/ответ) — только в подробном режиме, отдельной DEBUG-строкой.

Настройки — только переменные окружения:

    LOG_ENABLED=0        писать ли файлы логов (в stdout лог идёт всегда)
    LOG_PATH=/app/logs   каталог логов
    LOG_VERBOSE=1        писать запрос/ответ целиком
    LOG_LEVEL=DEBUG      уровень общего лога
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

# Значения по умолчанию, если переменные окружения не заданы.
DEFAULT_LOG_PATH = "logs"
DEFAULT_LOG_ENABLED = True
DEFAULT_LOG_VERBOSE = False
DEFAULT_LOG_LEVEL = "INFO"

LOG_FORMAT = "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3

# Ключи, значения которых не пишем никогда и ни в каком режиме.
SECRET_MARKERS = ("token", "password", "secret", "key", "authorization")
MASK = "***"
# Секреты встречаются и внутри тел запросов/ответов ("accessToken": "…"),
# где ключом поля лога их не отловить.
SECRET_JSON = re.compile(
    r'("[^"]*(?:%s)[^"]*"\s*:\s*)"[^"]*"' % "|".join(SECRET_MARKERS),
    re.IGNORECASE,
)

# Длина значения в короткой строке и в подробностях.
SHORT_LIMIT = 120
DETAIL_LIMIT = 4000

# Библиотеки, чей внутренний лог интересен только в подробном режиме.
NOISY_LOGGERS = ("httpx", "httpcore", "urllib3", "aiosmtplib", "asyncio", "aiogram")


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _log_dir() -> Path:
    path = Path(os.getenv("LOG_PATH") or DEFAULT_LOG_PATH)
    # Относительный путь — от корня проекта: иначе каталог логов появляется
    # там, откуда запустили процесс (в том числе внутри пакетов с кодом).
    return path if path.is_absolute() else PROJECT_ROOT / path


LOG_DIR = _log_dir()
ENABLED = _env_flag("LOG_ENABLED", DEFAULT_LOG_ENABLED)
VERBOSE = _env_flag("LOG_VERBOSE", DEFAULT_LOG_VERBOSE)
LEVEL = (os.getenv("LOG_LEVEL") or DEFAULT_LOG_LEVEL).upper()

_configured = False


def _file_handler(name: str) -> logging.Handler:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        LOG_DIR / f"{name}.log", maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    return handler


def setup_logging() -> None:
    """Настроить логирование процесса: stdout + `app.log`. Вызывать один раз на старте."""
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
        root.addHandler(_file_handler("app"))

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

    def skipped(self, reason: str) -> None:
        """Вызова не было: не настроен канал, нечего отправлять и т.п."""
        self._status = "skipped"
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
    """Обернуть вызов внешнего сервиса одной строкой лога.

    Пример:
        with integration_call("broker", "get_positions", account=account_id) as call:
            positions = ...
            call.add(shares=len(positions.shares))
            call.detail(response=positions)

    Исключение внутри блока логируется как `status=error` и пробрасывается дальше.
    """
    call = IntegrationCall(integration_logger(service), operation, params)
    try:
        yield call
    except Exception as error:
        call.write(error)
        raise
    else:
        call.write()
