from dataclasses import dataclass

from src.models.instrument import InstrumentBase


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


