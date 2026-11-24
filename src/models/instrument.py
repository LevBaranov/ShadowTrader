from dataclasses import dataclass


@dataclass()
class InstrumentBase:
    """
    Базовый дата класс для актива. Содержит основные поля финансового инструмента
    """

    uid: str
    # FIGI может отсутствовать (в справочнике БД храним NULL).
    figi: str | None
    ticker: str
    lot_size: int
    isin: str | None
    type: str

