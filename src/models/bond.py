from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum

from src.models.instrument import InstrumentBase


class BondEventType(str, Enum):
    """Корпоративные события по облигации, о которых предупреждаем владельца."""

    OFFER = "Оферта"
    OFFER_START = "Подача заявок на оферту"
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
    offer_date: date | None
    call_option_date: date | None
    put_option_date: date | None
    buy_back_price: float
    isin: str | None = None
    # Дата, когда открывается окно подачи заявок на оферту (bondization).
    offer_start_date: date | None = None

    def __post_init__(self):
        """Приводит строковые даты из API Мосбиржи к типу date."""
        self.offer_date = parse_moex_date(self.offer_date)
        self.call_option_date = parse_moex_date(self.call_option_date)
        self.put_option_date = parse_moex_date(self.put_option_date)
        self.offer_start_date = parse_moex_date(self.offer_start_date)

    def events(self) -> list[BondEvent]:
        """Известные события по бумаге (без фильтра по дате).

        OFFERDATE у Мосбиржи чаще всего и есть put-оферта, а PUTOPTIONDATE
        дублирует её как fallback; используем обе без повторения.
        Отдельно — дата, когда открывается окно подачи заявок на оферту.
        """
        offer_raw = self.offer_date
        if offer_raw is None:
            offer_raw = self.put_option_date

        pairs = (
            (BondEventType.OFFER, offer_raw),
            (BondEventType.OFFER_START, self.offer_start_date),
            (BondEventType.CALL_OPTION, self.call_option_date),
        )

        events = []
        seen: set[tuple[BondEventType, date]] = set()
        for event_type, raw_date in pairs:
            event_date = parse_moex_date(raw_date)
            if event_date is None:
                continue
            key = (event_type, event_date)
            if key in seen:
                continue
            seen.add(key)
            events.append(BondEvent(type=event_type, date=event_date))

        return events


@dataclass()
class Bond(InstrumentBase):
    """
    Дата класс описывающий облигацию с данными от брокера и Мосбиржи
    """

    offer_date: date | None
    call_option_date: date | None
    put_option_date: date | None
    buy_back_price: float
    # Короткое название с биржи и количество бумаг на счёте — для отчётов клиентам.
    short_name: str | None = None
    balance: int = 0
    # Предстоящие события (оферта, колл-опцион), отсортированы по дате.
    events: list[BondEvent] = field(default_factory=list)


BOND_EVENT_LABELS = {
    "OFFER": "оферта",
    "OFFER_START": "начало подачи заявок на оферту",
    "CALL_OPTION": "колл-опцион",
}
