"""auth identities: способы входа как отдельная сущность, telegram link requests, TaskType.REBALANCE

Revision ID: c4d81f2ae930
Revises: b7e3a9c41f02
Create Date: 2026-07-26 18:00:00.000000

Downgrade — best effort: telegram-only пользователи (без EMAIL-identity) получат
email = '' и нарушат уникальность, если их больше одного.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c4d81f2ae930'
down_revision: Union[str, Sequence[str], None] = 'b7e3a9c41f02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    authprovider = postgresql.ENUM('EMAIL', 'TELEGRAM', name='authprovider', create_type=False)
    authprovider.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'auth_identities',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('provider', postgresql.ENUM(name='authprovider', create_type=False), nullable=False),
        sa.Column('external_id', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('verification_code_hash', sa.String(), nullable=True),
        sa.Column('verification_code_expires_at', sa.DateTime(), nullable=True),
        sa.Column('verification_attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'external_id'),
    )

    # Бэкфилл: существующие поля входа переезжают в identities.
    op.execute("""
        INSERT INTO auth_identities (
            id, user_id, provider, external_id, password_hash, verified_at,
            verification_code_hash, verification_code_expires_at, verification_attempts,
            created_at, updated_at
        )
        SELECT gen_random_uuid(), id, 'EMAIL', email, password_hash, email_verified_at,
               verification_code_hash, verification_code_expires_at, verification_attempts,
               now(), now()
        FROM users
        WHERE email IS NOT NULL AND email <> ''
    """)
    op.execute("""
        INSERT INTO auth_identities (
            id, user_id, provider, external_id, password_hash, verified_at,
            verification_attempts, created_at, updated_at
        )
        SELECT gen_random_uuid(), id, 'TELEGRAM', telegram_id::text, NULL, now(),
               0, now(), now()
        FROM users
        WHERE telegram_id IS NOT NULL
    """)

    op.drop_column('users', 'verification_attempts')
    op.drop_column('users', 'verification_code_expires_at')
    op.drop_column('users', 'verification_code_hash')
    op.drop_column('users', 'email_verified_at')
    op.drop_column('users', 'password_hash')
    op.drop_column('users', 'email')
    op.drop_column('users', 'telegram_id')

    op.create_table(
        'telegram_link_requests',
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('code_hash', sa.String(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_id'),
    )

    # ADD VALUE не работает внутри транзакции миграции.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'REBALANCE'")

    # Задачи со старым форматом params (account_id брокера строкой из toml-мира)
    # новый планировщик не понимает — отключаем, пользователь включит заново из бота.
    op.execute("""
        UPDATE task SET disabled_date = now()
        WHERE task_type = 'BOND_EVENTS_MONITOR'
          AND disabled_date IS NULL
          AND params ? 'broker_account_id'
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('users', sa.Column('telegram_id', sa.BigInteger(), nullable=True))
    op.add_column('users', sa.Column('email', sa.String(), nullable=True))
    op.add_column('users', sa.Column('password_hash', sa.String(), nullable=True))
    op.add_column('users', sa.Column('email_verified_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('verification_code_hash', sa.String(), nullable=True))
    op.add_column('users', sa.Column('verification_code_expires_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('verification_attempts', sa.Integer(), server_default='0', nullable=False))

    op.execute("""
        UPDATE users u SET
            email = ai.external_id,
            password_hash = ai.password_hash,
            email_verified_at = ai.verified_at,
            verification_code_hash = ai.verification_code_hash,
            verification_code_expires_at = ai.verification_code_expires_at,
            verification_attempts = ai.verification_attempts
        FROM auth_identities ai
        WHERE ai.user_id = u.id AND ai.provider = 'EMAIL'
    """)
    op.execute("""
        UPDATE users u SET telegram_id = ai.external_id::bigint
        FROM auth_identities ai
        WHERE ai.user_id = u.id AND ai.provider = 'TELEGRAM'
    """)
    op.execute("UPDATE users SET email = '' WHERE email IS NULL")
    op.execute("UPDATE users SET password_hash = '' WHERE password_hash IS NULL")
    op.alter_column('users', 'email', nullable=False)
    op.alter_column('users', 'password_hash', nullable=False)
    op.create_unique_constraint(None, 'users', ['email'])
    op.create_unique_constraint(None, 'users', ['telegram_id'])

    op.drop_table('telegram_link_requests')
    op.drop_table('auth_identities')
    sa.Enum(name='authprovider').drop(op.get_bind(), checkfirst=True)
    # Значение REBALANCE из enum tasktype убрать нельзя — оставляем.
