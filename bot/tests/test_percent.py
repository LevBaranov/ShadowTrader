"""Тесты перевода долей в проценты и обратно.

API хранит долю (0.003 = 0,3 %), пользователь в боте вводит и видит проценты.
"""
from decimal import Decimal

import pytest

from bot.percent import fraction_to_percent, parse_percent


class TestFractionToPercent:

    @pytest.mark.parametrize("fraction, expected", [
        ("0.003", "0.3"),
        ("0.05", "5"),
        ("0", "0"),
        ("0.0005", "0.05"),
        ("0.1", "10"),
        # Целые не должны превращаться в экспоненту (3E+1).
        ("0.3", "30"),
    ])
    def test_formats(self, fraction, expected):
        assert fraction_to_percent(fraction) == expected

    def test_accepts_decimal_and_float(self):
        assert fraction_to_percent(Decimal("0.003")) == "0.3"
        assert fraction_to_percent(0.003) == "0.3"

    def test_broken_value_is_zero(self):
        assert fraction_to_percent(None) == "0"
        assert fraction_to_percent("не число") == "0"


class TestParsePercent:

    @pytest.mark.parametrize("text, expected", [
        ("0.3", "0.003"),
        ("5", "0.05"),
        ("0", "0"),
        # Запятая как разделитель — русская раскладка.
        ("0,3", "0.003"),
        (" 0.3 ", "0.003"),
    ])
    def test_parses(self, text, expected):
        assert parse_percent(text) == Decimal(expected)

    @pytest.mark.parametrize("text", ["", None, "много", "-1", "100", "150", "0.3%"])
    def test_rejects(self, text):
        assert parse_percent(text) is None

    def test_round_trip(self):
        """Показали проценты, пользователь их вернул — доля та же."""
        assert parse_percent(fraction_to_percent("0.003")) == Decimal("0.003")
