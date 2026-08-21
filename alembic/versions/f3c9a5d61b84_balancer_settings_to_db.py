"""Параметры балансировщика из toml — в БД: комиссия на брокера,
delta и min_lots_to_keep на стратегию.

Revision ID: f3c9a5d61b84
Revises: e1f4c8b27d55
Create Date: 2026-08-04 15:00:00.000000

Последние живые настройки из секции [balancer] переезжают к своим владельцам:

* users_broker.commission — тариф брокера, один для всех его счетов и стратегий;
* users_strategy.delta и .min_lots_to_keep — про то, как балансировать
  конкретный портфель.

Все три хранятся так же, как в toml (комиссия и delta — долей: 0.003 = 0,3 %,
0.05 = 5 %), поэтому расчёт не меняется. server_default повторяет прежние
значения из prod.toml-example, так что существующим брокерам и стратегиям
поведение сохраняется. Кто держал в toml нестандартные значения — правит их
в настройках брокера и стратегии.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3c9a5d61b84'
down_revision: Union[str, Sequence[str], None] = 'e1f4c8b27d55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users_broker',
        sa.Column(
            'commission',
            sa.Numeric(6, 5),
            nullable=False,
            server_default='0.003',
        ),
    )

    op.add_column(
        'users_strategy',
        sa.Column('delta', sa.Numeric(5, 4), nullable=False, server_default='0.05'),
    )
    op.add_column(
        'users_strategy',
        sa.Column('min_lots_to_keep', sa.Integer(), nullable=False, server_default='1'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users_strategy', 'min_lots_to_keep')
    op.drop_column('users_strategy', 'delta')
    op.drop_column('users_broker', 'commission')
