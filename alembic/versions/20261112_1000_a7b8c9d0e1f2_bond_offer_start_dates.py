"""Даты начала подачи заявок на оферту и задачи MOEX_BONDS_OFFER_DATE_SYNC / NOTIFY_START_OFFER_DATE.

Revision ID: a7b8c9d0e1f2
Revises: d9e1f2a3b4c5
Create Date: 2026-11-12 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'd9e1f2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'MOEX_BONDS_OFFER_DATE_SYNC'")
        op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'NOTIFY_START_OFFER_DATE'")
    op.add_column(
        'moex_bonds',
        sa.Column('offer_start_date', sa.Date(), nullable=True),
    )


def downgrade() -> None:
    # Значение из enum tasktype убрать нельзя — оставляем.
    op.drop_column('moex_bonds', 'offer_start_date')
