"""Частичные UNIQUE справочника брокера: только живые строки.

Revision ID: d4e7a1c9b2f3
Revises: b3e8f5c2a9d1
Create Date: 2026-10-05 12:00:00.000000

Полный UNIQUE(ticker, sandbox) ломал refresh при ротации uid брокером
(один тикер — новый uid, облигации ticker==isin, кейс RU000A10B354):
INSERT новой строки конфликтовал со строкой, которую тот же replace_all
собирался мягко удалить, а также с уже мягко удалёнными строками.
Тот же риск был у UNIQUE(uid, sandbox).

Меняем оба ограничения на частичные UNIQUE-индексы WHERE deleted_at IS NULL:
живые тикеры/uid уникальны в контуре, удалённая история — нет.
Код replace_all дополнительно переиспользует живую строку тикера in place
при ротации uid, так что миграция — второй рубеж, а не единственный фикс.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e7a1c9b2f3'
down_revision: Union[str, Sequence[str], None] = 'b3e8f5c2a9d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(
        'uq_broker_instruments_uid_sandbox',
        'broker_instruments',
        type_='unique',
    )
    op.drop_constraint(
        'uq_broker_instruments_ticker_sandbox',
        'broker_instruments',
        type_='unique',
    )
    op.create_index(
        'uq_broker_instruments_uid_sandbox',
        'broker_instruments',
        ['uid', 'sandbox'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )
    op.create_index(
        'uq_broker_instruments_ticker_sandbox',
        'broker_instruments',
        ['ticker', 'sandbox'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        'uq_broker_instruments_ticker_sandbox',
        table_name='broker_instruments',
    )
    op.drop_index(
        'uq_broker_instruments_uid_sandbox',
        table_name='broker_instruments',
    )
    # Упадёт, если за время жизни частичных индексов накопились дубли среди
    # удалённых строк, — это ожидаемо: полный UNIQUE историю не допускает.
    op.create_unique_constraint(
        'uq_broker_instruments_uid_sandbox',
        'broker_instruments',
        ['uid', 'sandbox'],
    )
    op.create_unique_constraint(
        'uq_broker_instruments_ticker_sandbox',
        'broker_instruments',
        ['ticker', 'sandbox'],
    )
