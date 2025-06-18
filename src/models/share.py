from dataclasses import dataclass, field, asdict
import pandas as pd
from typing import List

@dataclass()
class Share:

    uid: str
    figi: str
    ticker: str
    lot_size: int
    isin: str

@dataclass
class ShareList:
    items: List[Share] = field(default_factory=list)

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([asdict(item) for item in self.items])

