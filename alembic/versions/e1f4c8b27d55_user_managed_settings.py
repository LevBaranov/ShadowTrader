"""Настройки в управляемой пользователем зоне: max_cash стратегии,
порог автобалансировки в params задачи, канал уведомлений у пользователя.

Revision ID: e1f4c8b27d55
Revises: c4d81f2ae930
Create Date: 2026-08-04 12:00:00.000000

Переносим из toml ([balancer].max_cash) в БД и разделяем на две независимые
настройки:

* users_strategy.max_cash — неснижаемый остаток денег на счёте, балансировщик
  его не тратит (0 — как раньше, тратить всё);
* task.params.min_free_cash — порог свободного кэша, ниже которого планировщик
  не запускает автобалансировку. Существующим активным задачам проставляем 2000
  (значение из prod.toml-example), чтобы поведение не изменилось.

Плюс users.notification_channel — куда отправлять уведомления (раньше было
жёстко «Telegram, иначе почта»).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e1f4c8b27d55'
down_revision: Union[str, Sequence[str], None] = 'c4d81f2ae930'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Прежний дефолт из [balancer].max_cash в prod.toml-example.
LEGACY_MIN_FREE_CASH = 2000


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users_strategy',
        sa.Column('max_cash', sa.Integer(), nullable=False, server_default='0'),
    )

    notification_channel = postgresql.ENUM(
        'TELEGRAM', 'EMAIL', 'ALL', name='notificationchannel', create_type=False
    )
    notification_channel.create(op.get_bind(), checkfirst=True)

    op.add_column(
        'users',
        sa.Column(
            'notification_channel',
            postgresql.ENUM(name='notificationchannel', create_type=False),
            nullable=False,
            server_default='TELEGRAM',
        ),
    )

    # Прежний порог был общим для всех и жил в toml — фиксируем его в задачах,
    # дальше пользователь меняет через API.
    op.execute(f"""
        UPDATE task
        SET params = coalesce(params, '{{}}'::jsonb)
                     || '{{"min_free_cash": {LEGACY_MIN_FREE_CASH}}}'::jsonb
        WHERE task_type = 'REBALANCE'
          AND disabled_date IS NULL
          AND NOT (coalesce(params, '{{}}'::jsonb) ? 'min_free_cash')
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE task SET params = params - 'min_free_cash' WHERE params ? 'min_free_cash'")

    op.drop_column('users', 'notification_channel')
    sa.Enum(name='notificationchannel').drop(op.get_bind(), checkfirst=True)

    op.drop_column('users_strategy', 'max_cash')
