"""Тесты плана балансировки бота: сборка и сверка перед исполнением."""
import time

from bot.rebalance_plan import (
    EXPIRED,
    MISMATCH,
    MISSING,
    PLAN_TTL_SEC,
    make_plan,
    resolve_plan,
)


def test_make_plan_stamps_time():
    plan = make_plan("s-1", [{"type": "BUY", "ticker": "SBER", "quantity": 1}])

    assert plan["strategy_id"] == "s-1"
    assert plan["actions"] == [{"type": "BUY", "ticker": "SBER", "quantity": 1}]
    assert abs(plan["ts"] - time.time()) < 5


def test_resolve_ok():
    plan = make_plan("s-1", [{"type": "BUY", "ticker": "SBER", "quantity": 1}])

    actions, reason = resolve_plan(plan, "s-1")

    assert reason is None
    assert actions == [{"type": "BUY", "ticker": "SBER", "quantity": 1}]


def test_resolve_missing():
    assert resolve_plan(None, "s-1") == (None, MISSING)
    assert resolve_plan({}, "s-1") == (None, MISSING)


def test_resolve_mismatch():
    """План другой стратегии (две вкладки) — исполнять нельзя."""
    plan = make_plan("s-1", [])

    assert resolve_plan(plan, "s-2") == (None, MISMATCH)


def test_resolve_expired():
    plan = make_plan("s-1", [], now=time.time() - PLAN_TTL_SEC - 1)

    assert resolve_plan(plan, "s-1") == (None, EXPIRED)


def test_resolve_empty_actions_ok():
    """Пустой план валиден: сервер трактует его как отсутствие плана
    и пересчитывает сам (обратная совместимость)."""
    plan = make_plan("s-1", [])

    actions, reason = resolve_plan(plan, "s-1")

    assert reason is None
    assert actions == []
