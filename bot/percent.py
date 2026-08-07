"""Доли и проценты.

API хранит и принимает доли: комиссия 0.003 — это 0,3 %. Пользователю доля
непонятна, поэтому в боте всегда проценты, а перевод живёт здесь — чтобы
деление на 100 не размазывалось по обработчикам.
"""
from decimal import Decimal, InvalidOperation

# Сколько знаков после запятой оставляем в процентах: 0.00005 → 0.005 %.
PERCENT_PRECISION = 3


def fraction_to_percent(fraction) -> str:
    """Доля → проценты для показа: "0.003" → "0.3" (без незначащих нулей)."""
    try:
        value = Decimal(str(fraction)) * 100
    except (InvalidOperation, TypeError):
        return "0"

    # normalize() убирает хвостовые нули, quantize — лишние знаки.
    quantized = round(value, PERCENT_PRECISION).normalize()

    # normalize у целых даёт экспоненту (3E+1) — приводим к обычной записи.
    return f"{quantized:f}"


def parse_percent(text: str) -> Decimal | None:
    """Проценты из сообщения → доля для API. None — введено некорректно.

    Принимаем запятую как разделитель: так набирают на русской раскладке.
    Доля должна остаться в [0, 1), поэтому 100 % и выше не пропускаем — это
    почти наверняка ошибка ввода.
    """
    cleaned = (text or "").strip().replace(" ", "").replace(",", ".")
    if not cleaned:
        return None

    try:
        percent = Decimal(cleaned)
    except InvalidOperation:
        return None

    if not percent.is_finite() or percent < 0 or percent >= 100:
        return None

    return round(percent / 100, PERCENT_PRECISION + 2)
