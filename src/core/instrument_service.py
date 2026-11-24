"""Общий справочник инструментов брокера: сборка directory для расчёта.

Мета инструментов одинакова для всех пользователей, поэтому лежит в общей
таблице broker_instruments и обновляется токеном того пользователя, чей запрос
пришёл первым после протухания (TTL 24ч). Обновление всегда inline, в рамках
запроса: фоновых задач и использования чужих токенов нет, системный синк
составов (INDEX_SYNC) сюда не ходит вообще.

Ошибка refresh не роняет запрос: отдаём протухшие данные с warning, крайняя
мера — живой вызов в брокер на промахе (fallback живёт в TBroker).
"""
import asyncio
import logging
from datetime import datetime, timedelta

from typing import Callable

from src.core.verification import utcnow
from src.db.repositories.broker_instruments_repository import BrokerInstrumentsRepository
from src.models.instrument_directory import InstrumentDirectory, InstrumentMeta
from src.services.broker import TBroker

logger = logging.getLogger(__name__)

DIRECTORY_TTL = timedelta(hours=24)


def _utcnow() -> datetime:
    """Наивный UTC-now: в БД лежат наивные метки (server_default now())."""
    return utcnow()


class InstrumentService:
    def __init__(
        self,
        broker_factory: Callable | None = None,
        ttl: timedelta = DIRECTORY_TTL,
    ):
        self.broker_factory = broker_factory if broker_factory is not None else TBroker
        self.ttl = ttl

    async def ensure_directory(
        self,
        session,
        token: str,
        sandbox: bool,
        must_contain: set[str] | None = None,
        broker: TBroker | None = None,
    ) -> InstrumentDirectory:
        """Собрать directory контура: из БД, при необходимости обновив.

        must_contain — тикеры, обязанные быть в справочнике (состав индекса
        для расчёта): при промахе — разовый refresh и повторная сборка.
        """
        repo = BrokerInstrumentsRepository(session)
        directory = await self._build(repo, sandbox)

        if not self._needs_refresh(directory, must_contain or ()):
            return directory

        await self._refresh(repo, token, sandbox, broker=broker)
        return await self._build(repo, sandbox)

    def _needs_refresh(
        self, directory: InstrumentDirectory, must_contain: set[str]
    ) -> bool:
        """Нужен ли refresh: протух по TTL или нужных тикеров нет в справочнике."""
        if not self._is_fresh(directory):
            age = (
                f"{(_utcnow() - directory.updated_at)}"
                if directory.updated_at
                else "never synced"
            )
            logger.info("Справочник инструментов протух (%s) — refresh", age)
            return True
        missing = set(must_contain) - set(directory.by_ticker)
        if missing:
            logger.info(
                "Тикеров нет в справочнике (%s) — точечный refresh",
                ", ".join(sorted(missing)),
            )
            return True
        return False

    async def _build(self, repo, sandbox: bool) -> InstrumentDirectory:
        rows = await repo.get_alive(sandbox)
        by_ticker: dict[str, InstrumentMeta] = {}
        by_uid: dict[str, InstrumentMeta] = {}
        updated_at = None
        for row in rows:
            meta = InstrumentMeta(
                uid=row.uid,
                ticker=row.ticker,
                figi=row.figi,
                isin=row.isin,
                lot_size=row.lot_size,
                type=row.type,
            )
            by_ticker[row.ticker] = meta
            by_uid[row.uid] = meta
            if updated_at is None or (row.updated_at and row.updated_at > updated_at):
                updated_at = row.updated_at
        return InstrumentDirectory(
            sandbox=sandbox,
            updated_at=updated_at,
            by_ticker=by_ticker,
            by_uid=by_uid,
        )

    def _is_fresh(self, directory: InstrumentDirectory) -> bool:
        if not directory.by_ticker or directory.updated_at is None:
            return False
        return _utcnow() - directory.updated_at < self.ttl

    async def _refresh(self, repo, token: str, sandbox: bool, broker: TBroker | None = None) -> None:
        """Обновить таблицу токеном вызывающего. Ошибка — warning, запрос живёт дальше."""
        try:
            if broker is None:
                instruments = await asyncio.to_thread(self._fetch_instruments, token, sandbox)
            else:
                instruments = await asyncio.to_thread(broker.get_all_instruments)
            deduped = self._dedupe(instruments)
            await repo.replace_all(
                sandbox,
                [
                    (i.uid, i.ticker, i.figi, i.isin, i.lot_size, i.type)
                    for i in deduped
                ],
            )
            logger.info(
                "Справочник инструментов обновлён: %d записей (sandbox=%s)",
                len(deduped), sandbox,
            )
        except Exception:
            logger.exception("Refresh справочника инструментов не удался — работаем с протухшим")

    @staticmethod
    def _dedupe(instruments: list) -> list:
        """Убрать дубли тикеров из выдачи брокера: один тикер встречается
        с разными uid (допвыпуски облигаций). Первый выигрывает — uid-lookup
        для остальных остаётся через живой fallback."""
        seen: dict[str, object] = {}
        dupes: list[str] = []
        for instrument in instruments:
            if instrument.ticker in seen:
                dupes.append(instrument.ticker)
                continue
            seen[instrument.ticker] = instrument
        if dupes:
            logger.warning(
                "Дубли тикеров в выдаче брокера, берём первый: %s",
                ", ".join(sorted(set(dupes))),
            )
        return list(seen.values())

    def _fetch_instruments(self, token: str, sandbox: bool) -> list:
        broker = self.broker_factory(token=token, sandbox=sandbox)
        return broker.get_all_instruments()
