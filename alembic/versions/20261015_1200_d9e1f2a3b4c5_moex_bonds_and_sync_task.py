"""Справочник облигаций MOEX и значение MOEX_BONDS_SYNC.

Revision ID: d9e1f2a3b4c5
Revises: d4e7a1c9b2f3
Create Date: 2026-10-15 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd9e1f2a3b4c5'
down_revision: Union[str, Sequence[str], None] = 'd4e7a1c9b2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'MOEX_BONDS_SYNC'")
    op.create_table(
        'moex_bonds',
        sa.Column('secid', sa.String(length=36), nullable=False),
        sa.Column('short_name', sa.String(length=255), nullable=True),
        sa.Column('board_name', sa.String(length=32), nullable=True),
        sa.Column('lot_value', sa.Float(), nullable=True),
        sa.Column('offer_date', sa.Date(), nullable=True),
        sa.Column('call_option_date', sa.Date(), nullable=True),
        sa.Column('put_option_date', sa.Date(), nullable=True),
        sa.Column('buy_back_price', sa.Float(), nullable=True),
        sa.Column('isin', sa.String(length=32), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('moex_bonds')
