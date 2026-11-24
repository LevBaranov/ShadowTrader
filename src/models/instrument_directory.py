"""Снимок справочника инструментов брокера в памяти.

Проекция таблицы broker_instruments на время одного расчёта: async-слой
собирает directory заранее (см. InstrumentService.ensure_directory), sync-ядро
(PortfolioManager/TBroker в треде) только читает его — ходить в БД из треда
нельзя. Между запросами не кэшируется: свежесть проверяется при сборке.
"""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass()
class InstrumentMeta:
    uid: str
    ticker: str
    figi: str | None
    isin: str | None
    lot_size: int
    type: str


@dataclass()
class InstrumentDirectory:
    sandbox: bool
    # Когда справочник обновляли: по нему ensure_directory решает, не протух ли.
    updated_at: datetime | None
    by_ticker: dict[str, InstrumentMeta] = field(default_factory=dict)
    by_uid: dict[str, InstrumentMeta] = field(default_factory=dict)
