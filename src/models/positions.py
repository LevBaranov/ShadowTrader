from dataclasses import dataclass, field
import pandas as pd

@dataclass()
class Cash:
    units: int
    nano: int

    def to_float(self):
        return self.units + self.nano / 1e9

@dataclass()
class PositionsCash(Cash):
    currency: str

# @dataclass()
# class PositionsShare:
#     share_uid: str
#     figi: str
#     balance: int
#     last_price: Cash
#     lot_size: int
#     ticker: str

@dataclass()
class PositionsInstrument:
    """
    Дата класс, описывающий позицию по финансовому инструменту
    """
    uid: str
    figi: str
    balance: int
    last_price: Cash
    lot_size: int
    ticker: str
    type: str

@dataclass()
class Positions:
    cash: PositionsCash
    shares: list[PositionsInstrument] = field(default_factory=list)
    bonds: list[PositionsInstrument] = field(default_factory=list)

    def shares_to_dataframe(self) -> pd.DataFrame:
        data = []
        if self.shares:
            for share in self.shares:
                item = {
                    "share_uid": share.uid,
                    "figi": share.figi,
                    "balance": share.balance,
                    "last_price": share.last_price.to_float(),
                    "lot_size": share.lot_size,
                    "ticker": share.ticker
                }
                data.append(item)
            return pd.DataFrame(data)
        return  pd.DataFrame(columns=['share_uid', 'figi', 'balance', 'last_price', 'lot_size', 'ticker'])