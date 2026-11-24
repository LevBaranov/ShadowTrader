from datetime import date, datetime

from sqlalchemy import func, select

from src.core.verification import utcnow
from src.db.models.moex_bond import MoexBond as DBMoexBond
from src.models.bond import MoexBond as MarketBond
from src.services.stock_market import Moex


def _to_market_bond(row: DBMoexBond) -> MarketBond:
    return MarketBond(
        ticker=row.secid,
        short_name=row.short_name or row.secid,
        board_name=row.board_name or "",
        lot_value=row.lot_value or 0.0,
        offer_date=row.offer_date,
        call_option_date=row.call_option_date,
        put_option_date=row.put_option_date,
        buy_back_price=row.buy_back_price or 0.0,
        isin=row.isin,
        offer_start_date=row.offer_start_date,
    )


class MoexBondsRepository:
    def __init__(self, session):
        self.session = session

    async def get_all(self) -> list[MarketBond]:
        result = await self.session.execute(select(DBMoexBond))
        return [_to_market_bond(row) for row in result.scalars().all()]

    async def get_updated_at(self) -> datetime | None:
        result = await self.session.execute(select(func.max(DBMoexBond.updated_at)))
        return result.scalar_one_or_none()

    async def _start_dates_index(self) -> tuple[dict[str, date], dict[str, date]]:
        """Индексы дат подачи заявок по secid и isin — для сравнения с bondization."""
        result = await self.session.execute(select(DBMoexBond))
        by_secid: dict[str, date] = {}
        by_isin: dict[str, date] = {}
        for row in result.scalars().all():
            if row.offer_start_date is None:
                continue
            if row.secid:
                by_secid[row.secid] = row.offer_start_date
            if row.isin:
                by_isin[row.isin] = row.offer_start_date
        return by_secid, by_isin

    async def replace_all(self, bonds: list[MarketBond]) -> int:
        """Синхронизировать справочник: обновить/добавить, удалить исчезнувшие.

        Upsert вместо delete+insert: не плодит новые id и не оставляет таблицу
        пустой между запросами. Даты оферт из bondization — накопленные знания —
        переносим между версиями справочника.
        """
        try:
            result = await self.session.execute(select(DBMoexBond))
            existing_rows = list(result.scalars().all())
            existing = {row.secid: row for row in existing_rows}
            by_secid = {
                row.secid: row.offer_start_date
                for row in existing_rows
                if row.offer_start_date is not None
            }
            by_isin = {
                row.isin: row.offer_start_date
                for row in existing_rows
                if row.isin and row.offer_start_date is not None
            }

            now = utcnow()
            seen: set[str] = set()
            for bond in bonds:
                seen.add(bond.ticker)
                row = existing.get(bond.ticker)
                if row is None:
                    row = DBMoexBond(secid=bond.ticker)
                    self.session.add(row)
                row.short_name = bond.short_name
                row.board_name = bond.board_name
                row.lot_value = bond.lot_value
                row.offer_date = bond.offer_date or None
                row.call_option_date = bond.call_option_date or None
                row.put_option_date = bond.put_option_date or None
                row.buy_back_price = bond.buy_back_price
                row.isin = bond.isin
                row.offer_start_date = (
                    by_secid.get(bond.ticker)
                    or by_isin.get(bond.isin or "")
                )
                # Отметка синка: даже без изменения полей продлевает TTL кэша.
                row.updated_at = now

            for secid, row in existing.items():
                if secid not in seen:
                    await self.session.delete(row)

            await self.session.commit()
            return len(bonds)
        except Exception:
            await self.session.rollback()
            raise

    async def known_offer_start_dates(
            self, offers: list[tuple[str, str | None, date]]
    ) -> list[tuple[str, str | None, date]]:
        """Оферы, чья дата подачи заявок отличается от сохранённой в справочнике.

        Хранимая дата — состояние "разослано": совпадает -> задачу не создаём,
        отличается или неизвестна -> дата новая, по ней уведомляем.
        """
        by_secid, by_isin = await self._start_dates_index()
        return [
            (secid, isin, start_date)
            for secid, isin, start_date in offers
            if by_secid.get(secid) != start_date and by_isin.get(isin or "") != start_date
        ]

    async def update_offer_start_dates(
            self, offers: list[tuple[str, str | None, date]]
    ) -> int:
        """Сохранить даты начала подачи заявок из bondization (secid или isin)."""
        try:
            updated = 0
            for secid, isin, start_date in offers:
                condition = DBMoexBond.secid == secid
                if isin:
                    condition = condition | (DBMoexBond.isin == isin)
                stmt = select(DBMoexBond).where(condition)
                row = await self.session.scalar(stmt)
                if row is None or row.offer_start_date == start_date:
                    continue
                row.offer_start_date = start_date
                updated += 1
            await self.session.commit()
            return updated
        except Exception:
            await self.session.rollback()
            raise
