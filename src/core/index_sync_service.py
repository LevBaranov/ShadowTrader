"""Синхронизация составов индексов Мосбиржи в БД.

Состав (тикер/вес/название) тянется только из analytics-эндпоинта — рыночные
данные (цены/лоты) больше не запрашиваем: цены и лоты расчёт берёт у брокера.
Хранится только текущий слепок, истории нет: пустой ответ биржи — это ошибка,
старые строки при ней не трогаем.

Ошибки отдельных индексов не роняют весь синк: они перечисляются в итоговой
строке (она пишется в task_result). last_checked_date при этом обновляется —
следующая попытка завтра; стратегии тем временем прикрывает on-demand добор.
"""
import asyncio
import logging
from datetime import date
from decimal import Decimal, InvalidOperation

from src.db.models.stock_market_index import StockMarketsIndex
from src.db.repositories.index_composition_repository import IndexCompositionRepository
from src.db.repositories.users_strategy_repository import UsersStrategyRepository
from src.models.index_composition import CompositionRow, CompositionSnapshot
from src.services.stock_market import Moex

logger = logging.getLogger(__name__)

# Итоговые строки синка: пишутся в task_result, по ним видно состояние в логах.
RESULT_NOTHING_TO_SYNC = "no strategy indices to sync"


def _parse_tradedate(index_name: str, first_row: list) -> date:
    """Торговая дата состава — из первой строки analytics."""
    try:
        return date.fromisoformat(first_row[1])
    except (ValueError, TypeError, IndexError) as exc:
        raise ValueError(
            f"Moex returned bad tradedate for {index_name}: {first_row!r}"
        ) from exc


def _parse_row(index_name: str, row: list) -> tuple[str, str | None, Decimal] | None:
    """Одна строка analytics -> (ticker, shortname, weight). Битая — None."""
    try:
        _indexid, _tradedate, ticker, shortname, weight = row[:5]
        weight = Decimal(str(weight))
    except (ValueError, TypeError, InvalidOperation) as exc:
        logger.warning("Пропускаем битую строку состава %s: %r (%s)", index_name, row, exc)
        return None
    if not ticker:
        logger.warning("Пропускаем строку состава %s без тикера: %r", index_name, row)
        return None
    return ticker, shortname, weight


class IndexSyncService:
    def __init__(self, moex: Moex | None = None):
        self.moex = moex if moex is not None else Moex()

    def fetch_rows(self, index_name: str) -> tuple[date, list[tuple[str, str | None, Decimal]]]:
        """Состав индекса с Мосбиржи: (торговая дата, [(ticker, shortname, weight)]).

        Битые строки пропускаем с варнингом, пустой состав — ошибка.
        """
        data = self.moex.load_index_rows(index_name.upper())
        if not data:
            raise ValueError(f"Moex returned empty composition for {index_name}")

        tradedate = _parse_tradedate(index_name, data[0])
        rows = [_parse_row(index_name, row) for row in data]
        rows = [row for row in rows if row is not None]

        if not rows:
            raise ValueError(f"Moex returned no valid rows for {index_name}")

        return tradedate, rows

    async def sync_index(self, session, index_id, index_name: str) -> str:
        """Синкнуть один индекс: биржа (в треде) -> замена слепка в БД."""
        tradedate, rows = await asyncio.to_thread(self.fetch_rows, index_name)
        await IndexCompositionRepository(session).replace(index_id, tradedate, rows)
        return f"{index_name}: {len(rows)} tickers @ {tradedate.isoformat()}"

    async def sync_strategy_indices(self, session) -> str:
        """Синкнуть составы индексов, на которые есть стратегии."""
        indices = await UsersStrategyRepository(session).get_referenced_indices()
        if not indices:
            return RESULT_NOTHING_TO_SYNC

        synced: list[str] = []
        failed: list[str] = []
        # indices — плоские (id, name): rollback в replace() инвалидирует ORM,
        # и обращение к index_row.index_name после него падало бы MissingGreenlet.
        for index_id, index_name in indices:
            try:
                synced.append(await self.sync_index(session, index_id, index_name))
            except Exception as error:
                logger.exception("Index sync failed for %s", index_name)
                failed.append(f"{index_name}: {error}")

        result = f"synced: {len(synced)} indices"
        if synced:
            result += f" ({'; '.join(synced)})"
        if failed:
            result += f", failed: {len(failed)} ({'; '.join(failed)})"
        return result

    async def ensure_composition(self, session, index_row: StockMarketsIndex) -> CompositionSnapshot:
        """Состав индекса для расчёта: из БД, а если его нет — разово с биржи.

        Пустой состав после добора — ошибка: считать не по чему.
        """
        repo = IndexCompositionRepository(session)
        stored = await repo.get_by_index(index_row.id)
        if not stored:
            logger.info("Состава %s нет в БД — тянем разово с биржи", index_row.index_name)
            await self.sync_index(session, index_row.id, index_row.index_name)
            stored = await repo.get_by_index(index_row.id)
        if not stored:
            raise ValueError(f"No composition for index {index_row.index_name}")

        tradedate = index_row.composition_tradedate or stored[0].tradedate
        return CompositionSnapshot(
            index_name=index_row.index_name,
            tradedate=tradedate,
            rows=[
                CompositionRow(
                    ticker=row.ticker,
                    shortname=row.shortname or row.ticker,
                    weight=float(row.weight),
                )
                for row in stored
            ],
        )
