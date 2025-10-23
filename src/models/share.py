from dataclasses import dataclass, field, asdict
import pandas as pd
from typing import List

from src.models.instrument import InstrumentBase


@dataclass()
class Share(InstrumentBase):
    """
    Дата класс, описывающий акции с данными от брокера
    """



@dataclass
class ShareList:
    items: List[Share] = field(default_factory=list)

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([asdict(item) for item in self.items])

