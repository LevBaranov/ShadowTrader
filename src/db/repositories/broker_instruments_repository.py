import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.broker_instrument import BrokerInstrument

logger = logging.getLogger(__name__)


class BrokerInstrumentsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_alive(self, sandbox: bool) -> list[BrokerInstrument]:
        """Живые строки справочника контура (без помеченных удалёнными).

        Свежесть считает вызывающий (InstrumentService) максимумом updated_at
        загруженных строк — отдельного запроса не нужно.
        """
        result = await self.session.execute(
            select(BrokerInstrument)
            .where(BrokerInstrument.sandbox == sandbox)
            .where(BrokerInstrument.deleted_at.is_(None))
        )
        return list(result.scalars().all())

    async def replace_all(
        self,
        sandbox: bool,
        rows: list[tuple[str, str, str | None, str | None, int, str]],
    ) -> None:
        """Заменить справочник контура целиком одной транзакцией.

        rows — (uid, ticker, figi, isin, lot_size, type). Пришедшие строки
        обновляются (deleted_at снимается), отсутствующие в выдаче мягко
        удаляются. Истории нет. При ошибке — rollback, чтобы сессия осталась
        пригодной для дальнейшей работы вызывающего.

        Брокер переиспользует тикеры с новым uid (допвыпуски/перевыпуски
        облигаций, ticker==isin): строка с тем же тикером, но другим uid —
        это ротация, а не новая бумага. Такую строку переиспользуем in place
        (меняем uid), иначе INSERT падает на
        uq_broker_instruments_ticker_sandbox. Тот же приём спасает от
        конфликта с мягко удалёнными строками при старом полном UNIQUE.
        """
        try:
            result = await self.session.execute(
                select(BrokerInstrument).where(BrokerInstrument.sandbox == sandbox)
            )
            all_existing = list(result.scalars().all())
            by_uid: dict[str, BrokerInstrument] = {row.uid: row for row in all_existing}
            # Живые тикеры — для резолва ротаций. Удалённые держим отдельно,
            # чтобы переиспользовать их вместо INSERT при старом полном UNIQUE.
            by_ticker_alive: dict[str, BrokerInstrument] = {}
            deleted_by_ticker: dict[str, BrokerInstrument] = {}
            for row in all_existing:
                if row.deleted_at is None:
                    by_ticker_alive.setdefault(row.ticker, row)
                else:
                    deleted_by_ticker.setdefault(row.ticker, row)

            now = func.now()
            seen_tickers: set[str] = set()
            incoming_tickers: set[str] = set()
            for uid, ticker, figi, isin, lot_size, type_ in rows:
                # Защита от остаточных дублей в батче (сервис уже dedupe-ит):
                # берём первый, как и InstrumentService._dedupe.
                if ticker in seen_tickers:
                    continue
                seen_tickers.add(ticker)
                incoming_tickers.add(ticker)

                row_by_uid = by_uid.get(uid)
                if row_by_uid is not None:
                    if row_by_uid.ticker != ticker:
                        old_ticker = row_by_uid.ticker
                        other = by_ticker_alive.get(ticker)
                        if other is not None and other is not row_by_uid:
                            other.deleted_at = now
                            other.updated_at = now
                            by_ticker_alive.pop(ticker, None)
                        by_ticker_alive.pop(old_ticker, None)
                        if deleted_by_ticker.get(old_ticker) is row_by_uid:
                            deleted_by_ticker.pop(old_ticker, None)
                        row_by_uid.ticker = ticker
                        by_ticker_alive[ticker] = row_by_uid
                    row_by_uid.figi = figi
                    row_by_uid.isin = isin
                    row_by_uid.lot_size = lot_size
                    row_by_uid.type = type_
                    row_by_uid.deleted_at = None
                    row_by_uid.updated_at = now
                    deleted_by_ticker.pop(ticker, None)
                    continue

                row_by_ticker = by_ticker_alive.get(ticker)
                if row_by_ticker is not None:
                    old_uid = row_by_ticker.uid
                    by_uid.pop(old_uid, None)
                    row_by_ticker.uid = uid
                    row_by_ticker.figi = figi
                    row_by_ticker.isin = isin
                    row_by_ticker.lot_size = lot_size
                    row_by_ticker.type = type_
                    row_by_ticker.deleted_at = None
                    row_by_ticker.updated_at = now
                    by_uid[uid] = row_by_ticker
                    logger.info(
                        "Тикер %s: ротация uid %s -> %s (sandbox=%s)",
                        ticker, old_uid, uid, sandbox,
                    )
                    continue

                # Новый тикер+uid. При старом полном UNIQUE INSERT конфликтовал
                # бы с мягко удалённой строкой того же тикера — переиспользуем её.
                revived = deleted_by_ticker.pop(ticker, None)
                if revived is not None:
                    by_uid.pop(revived.uid, None)
                    revived.uid = uid
                    revived.figi = figi
                    revived.isin = isin
                    revived.lot_size = lot_size
                    revived.type = type_
                    revived.deleted_at = None
                    revived.updated_at = now
                    by_uid[uid] = revived
                    by_ticker_alive[ticker] = revived
                    continue

                new_row = BrokerInstrument(
                    uid=uid,
                    ticker=ticker,
                    figi=figi,
                    isin=isin,
                    lot_size=lot_size,
                    type=type_,
                    sandbox=sandbox,
                )
                self.session.add(new_row)
                by_uid[uid] = new_row
                by_ticker_alive[ticker] = new_row

            for row in all_existing:
                if row.ticker not in incoming_tickers and row.deleted_at is None:
                    row.deleted_at = now
                    row.updated_at = now

            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
