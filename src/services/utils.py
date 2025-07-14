import os
import json
import logging
import inspect
from functools import wraps
import time
from dataclasses import asdict, is_dataclass

from src.config import settings

### Функция для кэширования

def cache_data(ttl_seconds: int):
    """Декоратор для кэширования вызова метода с TTL."""
    def decorator(func):
        cache = None
        last_update = 0

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            nonlocal cache, last_update

            current_time = time.time()
            if cache is not None and (current_time - last_update) < ttl_seconds:
                return cache

            print(f"Обновляю кэш в {func.__name__}...")
            cache = func(self, *args, **kwargs)
            last_update = current_time
            return cache
        return wrapper
    return decorator


### Функции для сбора логов

def default_serializer(obj):
    if is_dataclass(obj):
        return asdict(obj)
    return str(obj)

def log_integration(name: str, request: dict, response: dict):

    integration_logger.debug(json.dumps({
        "name": name,
        "request": request,
        "response": response,
    }, ensure_ascii=False, default=default_serializer, indent=2))


def log_response():
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            bound_args = inspect.signature(func).bind(*args, **kwargs)
            bound_args.apply_defaults()
            request_data = dict(bound_args.arguments)

            try:
                result = func(*args, **kwargs)
                response_data = result
            except Exception as e:
                response_data = {"error": str(e)}
                raise
            finally:
                log_integration(
                    func.__name__,
                    request_data,
                    response_data
                )

            return result
        return wrapper
    return decorator



INTEGRATION_LOG_PATH = settings.logging.path + settings.broker.log_file
INTEGRATION_LOG_ENABLED = settings.logging.enabled

integration_logger = logging.getLogger("broker_integration")
integration_logger.setLevel(logging.DEBUG if INTEGRATION_LOG_ENABLED else logging.CRITICAL)

if not integration_logger.handlers:
    os.makedirs(os.path.dirname(INTEGRATION_LOG_PATH), exist_ok=True)
    handler = logging.FileHandler(INTEGRATION_LOG_PATH, encoding="utf-8")
    formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s')
    handler.setFormatter(formatter)
    integration_logger.addHandler(handler)