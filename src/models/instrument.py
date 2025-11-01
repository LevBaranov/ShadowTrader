from dataclasses import dataclass


@dataclass()
class InstrumentBase:
    """
    Базовый дата класс для актива. Содержит основные поля финансового инструмента
    """

    uid: str
    figi: str
    ticker: str
    lot_size: int
    isin: str | None
    type: str

