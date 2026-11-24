"""Слепок состава индексов в БД + системная задача ежедневного синка.

Revision ID: 9f4c2a1b7d3e
Revises: f3c9a5d61b84
Create Date: 2026-09-29 12:00:00.000000

Новая таблица index_composition — состав индекса (тикер/вес/название) без цен:
цены и лоты при каждом расчёте подтягиваются у брокера. Хранится только
текущий слепок, истории нет. На stock_markets_index — мета последнего синка.

Значения енамов добавляются через autocommit_block: ALTER TYPE ... ADD VALUE
не работает внутри транзакции миграции (прецедент — c4d81f2ae930).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f4c2a1b7d3e'
down_revision: Union[str, Sequence[str], None] = 'f3c9a5d61b84'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ADD VALUE не работает внутри транзакции миграции.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'INDEX_SYNC'")
        op.execute("ALTER TYPE schedulefrequency ADD VALUE IF NOT EXISTS 'DAILY'")

    op.create_table(
        'index_composition',
        sa.Column('index_id', sa.UUID(), nullable=False),
        sa.Column('ticker', sa.String(), nullable=False),
        sa.Column('shortname', sa.String(), nullable=True),
        sa.Column('weight', sa.Numeric(8, 4), nullable=False),
        sa.Column('tradedate', sa.Date(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['index_id'], ['stock_markets_index.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('index_id', 'ticker', name='uq_index_composition_index_ticker'),
    )
    op.create_index('ix_index_composition_index_id', 'index_composition', ['index_id'])

    op.add_column(
        'stock_markets_index',
        sa.Column('composition_updated_at', sa.DateTime(), nullable=True),
    )
    op.add_column(
        'stock_markets_index',
        sa.Column('composition_tradedate', sa.Date(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('stock_markets_index', 'composition_tradedate')
    op.drop_column('stock_markets_index', 'composition_updated_at')
    op.drop_index('ix_index_composition_index_id', table_name='index_composition')
    op.drop_table('index_composition')

    # Значения INDEX_SYNC и DAILY из енамов убрать нельзя — оставляем.
