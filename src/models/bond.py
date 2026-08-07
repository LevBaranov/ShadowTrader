from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum

from src.models.instrument import InstrumentBase


class BondEventType(str, Enum):
    """Корпоративные события по облигации, о которых предупреждаем владельца."""

    OFFER = "Оферта"
    CALL_OPTION = "Колл-опцион"


@dataclass()
class BondEvent:
    """Предстоящее событие по облигации: что и когда."""

    type: BondEventType
    date: date


def parse_moex_date(value) -> date | None:
    """Дата события из выгрузки Мосбиржи.

    Мосбиржа отдаёт даты строкой YYYY-MM-DD, а отсутствие события — None,
    пустой строкой или нулевой датой, поэтому разбираем защитно.
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


@dataclass()
class MoexBond:
    """
    Дата класс описывающий облигацию с данными от Мосбиржи
    """

    ticker: str
    short_name: str
    board_name: str
    lot_value: float
    offer_date: str
    call_option_date: str
    put_option_date: str
    buy_back_price: float

    def events(self) -> list[BondEvent]:
        """Известные события по бумаге (без фильтра по дате)."""
        pairs = (
            (BondEventType.OFFER, self.offer_date),
            (BondEventType.CALL_OPTION, self.call_option_date),
        )

        events = []
        for event_type, raw_date in pairs:
            event_date = parse_moex_date(raw_date)
            if event_date is not None:
                events.append(BondEvent(type=event_type, date=event_date))

        return events


@dataclass()
class Bond(InstrumentBase):
    """
    Дата класс описывающий облигацию с данными от брокера и Мосбиржи
    """

    offer_date: str
    call_option_date: str
    put_option_date: str
    buy_back_price: float
    # Короткое название с биржи и количество бумаг на счёте — для отчётов клиентам.
    short_name: str | None = None
    balance: int = 0
    # Предстоящие события (оферта, колл-опцион), отсортированы по дате.
    events: list[BondEvent] = field(default_factory=list)
