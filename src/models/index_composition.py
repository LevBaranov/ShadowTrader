"""Слепок состава индекса.

Состав (тикер/вес/название) хранится в БД и обновляется ежедневной системной
задачей INDEX_SYNC. Цены и лоты в слепок не входят — их при каждом расчёте
подтягивает PortfolioManager у брокера.
"""
from dataclasses import dataclass, field
from datetime import date


@dataclass
class CompositionRow:
    ticker: str
    shortname: str
    weight: float


@dataclass
class CompositionSnapshot:
    index_name: str
    tradedate: date | None
    rows: list[CompositionRow] = field(default_factory=list)

    @property
    def tickers(self) -> set[str]:
        """Тикеры состава — для точечного добора справочника."""
        return {row.ticker for row in self.rows}
