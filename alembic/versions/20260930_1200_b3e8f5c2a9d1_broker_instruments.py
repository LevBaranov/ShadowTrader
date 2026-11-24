"""Общий справочник инструментов брокера для всех пользователей.

Revision ID: b3e8f5c2a9d1
Revises: 9f4c2a1b7d3e
Create Date: 2026-09-30 12:00:00.000000

Мета инструментов (uid/figi/ticker/lot/isin) одинакова для всех владельцев
счетов, поэтому хранится один раз и читается горячим путём расчёта вместо
get_all_shares/get_all_instruments на каждый запрос.

Песочница и бой — разные вселенные инструментов: строки помечены флагом
sandbox, запросы читают и обновляют только свой контур. Пропавшие из выдачи
брокера инструменты не удаляем физически (held-бумаги живут в портфелях
после делистинга), а помечаем deleted_at.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3e8f5c2a9d1'
down_revision: Union[str, Sequence[str], None] = '9f4c2a1b7d3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'broker_instruments',
        sa.Column('uid', sa.String(), nullable=False),
        sa.Column('ticker', sa.String(), nullable=False),
        sa.Column('figi', sa.String(), nullable=True),
        sa.Column('isin', sa.String(), nullable=True),
        sa.Column('lot_size', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('sandbox', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('uid', 'sandbox', name='uq_broker_instruments_uid_sandbox'),
        sa.UniqueConstraint('ticker', 'sandbox', name='uq_broker_instruments_ticker_sandbox'),
    )
    op.create_index(
        'ix_broker_instruments_sandbox_ticker',
        'broker_instruments',
        ['sandbox', 'ticker'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_broker_instruments_sandbox_ticker', table_name='broker_instruments')
    op.drop_table('broker_instruments')
