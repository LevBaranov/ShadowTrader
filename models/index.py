from dataclasses import dataclass, field, asdict
import pandas as pd

@dataclass()
class IndexItem:

    ticker: str
    shortnames: str
    weight: float
    lot_size: int
    isin: str
    last_price: float

@dataclass()
class Index:

    name: str
    date: str
    items: list[IndexItem] = field(default_factory=list)

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([asdict(i) for i in self.items])

