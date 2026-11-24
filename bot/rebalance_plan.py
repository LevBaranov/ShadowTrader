"""План балансировки для исполнения из бота: показал = исполнил.

Telegram отдаёт в callback_data максимум 64 байта — список действий туда не
влезает. Поэтому превью запоминается в FSM-памяти бота (view), а исполнение
(exec) сверяет сохранённое: план есть, стратегия та же, возраст в пределах TTL.
Не сошлось — просим открыть стратегию заново вместо молчаливого пересчёта.

Память процесса: рестарт бота стирает планы — exec тогда честно отвечает
PLAN_STALE. Две реплики бота не поддерживаются (MemoryStorage).

Пустой план валиден и означает «пересчитай на сервере»: бэкенд трактует
пустой список как отсутствие плана (обратная совместимость).
"""
import time
from typing import Literal

# План живёт 15 минут: старше — уже не «то, что видел пользователь».
# Значение продублировано в bot/texts.py (PLAN_STALE) — менять вместе.
PLAN_TTL_SEC = 15 * 60

PlanRejectReason = Literal["missing", "mismatch", "expired"]
MISSING: PlanRejectReason = "missing"
MISMATCH: PlanRejectReason = "mismatch"
EXPIRED: PlanRejectReason = "expired"


def make_plan(strategy_id: str, actions: list[dict], now: float | None = None) -> dict:
    """Слепок показанного плана для FSM."""
    return {
        "strategy_id": strategy_id,
        "actions": list(actions or []),
        "ts": now if now is not None else time.time(),
    }


def resolve_plan(stored, strategy_id: str, now: float | None = None):
    """Проверить сохранённый план перед исполнением.

    :return: (actions, None) — можно исполнять; (None, причина) — нельзя.
    """
    now = now if now is not None else time.time()
    if not isinstance(stored, dict):
        return None, MISSING
    if stored.get("strategy_id") is None:
        return None, MISSING
    if stored.get("strategy_id") != strategy_id:
        return None, MISMATCH
    ts = stored.get("ts")
    if not isinstance(ts, (int, float)):
        return None, EXPIRED
    if now - ts > PLAN_TTL_SEC:
        return None, EXPIRED
    actions = stored.get("actions") or []
    return list(actions), None
