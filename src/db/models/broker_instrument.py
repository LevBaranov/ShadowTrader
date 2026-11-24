from datetime import datetime

from sqlalchemy import Index, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.database import Base


class BrokerInstrument(Base):
    """Строка общего справочника инструментов брокера.

    Мета одинакова для всех пользователей, контур (песочница/бой) разделяется
    флагом sandbox. Пропавшие из выдачи брокера строки помечаем deleted_at,
    физически не удаляем: held-бумаги живут в портфелях после делистинга.
    """

    __tablename__ = 'broker_instruments'
    # Зеркало миграции d4e7a1c9b2f3: уникальность uid/тикера — в разрезе контура
    # и только среди живых строк (deleted_at IS NULL). Мягко удалённые строки
    # историю не блокируют: тикер с новым uid переиспользует живую строку
    # (см. BrokerInstrumentsRepository.replace_all), resurrection — revive.
    __table_args__ = (
        Index(
            'uq_broker_instruments_uid_sandbox',
            'uid', 'sandbox',
            unique=True,
            postgresql_where=text('deleted_at IS NULL'),
        ),
        Index(
            'uq_broker_instruments_ticker_sandbox',
            'ticker', 'sandbox',
            unique=True,
            postgresql_where=text('deleted_at IS NULL'),
        ),
        Index('ix_broker_instruments_sandbox_ticker', 'sandbox', 'ticker'),
    )

    uid: Mapped[str] = mapped_column(nullable=False)
    ticker: Mapped[str] = mapped_column(nullable=False)
    figi: Mapped[str | None] = mapped_column(nullable=True)
    isin: Mapped[str | None] = mapped_column(nullable=True)
    lot_size: Mapped[int] = mapped_column(nullable=False)
    # Тип инструмента у брокера: share/bond.
    type: Mapped[str] = mapped_column(nullable=False)
    sandbox: Mapped[bool] = mapped_column(nullable=False, default=False, server_default='false')
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
