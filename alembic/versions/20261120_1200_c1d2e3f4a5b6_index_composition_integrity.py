"""Правила целостности index_composition: вес >= 0 и каскадное удаление.

Revision ID: c1d2e3f4a5b6
Revises: a7b8c9d0e1f2
Create Date: 2026-11-20 12:00:00.000000

Модель IndexComposition объявляет CheckConstraint и FK ondelete='CASCADE',
а исходная миграция — нет. Добавляем отдельной ревизией, чтобы не менять
уже применённую миграцию.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        'ck_index_composition_weight_non_negative',
        'index_composition',
        'weight >= 0',
    )
    # FK из исходной миграции создан без имени — Postgres назвал его по умолчанию.
    op.drop_constraint(
        'index_composition_index_id_fkey',
        'index_composition',
        type_='foreignkey',
    )
    op.create_foreign_key(
        'fk_index_composition_index_id',
        'index_composition',
        'stock_markets_index',
        ['index_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_index_composition_index_id',
        'index_composition',
        type_='foreignkey',
    )
    op.create_foreign_key(
        'index_composition_index_id_fkey',
        'index_composition',
        'stock_markets_index',
        ['index_id'],
        ['id'],
    )
    op.drop_constraint(
        'ck_index_composition_weight_non_negative',
        'index_composition',
        type_='check',
    )
