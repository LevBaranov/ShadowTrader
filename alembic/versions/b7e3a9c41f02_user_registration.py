"""user registration: nullable telegram_id, email verification fields

Revision ID: b7e3a9c41f02
Revises: 1ef666b8ad4e
Create Date: 2026-07-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e3a9c41f02'
down_revision: Union[str, Sequence[str], None] = '1ef666b8ad4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Пользователи из веб-регистрации существуют без Telegram.
    op.alter_column('users', 'telegram_id', existing_type=sa.Integer(), nullable=True)

    op.add_column('users', sa.Column('email_verified_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('verification_code_hash', sa.String(), nullable=True))
    op.add_column('users', sa.Column('verification_code_expires_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('verification_attempts', sa.Integer(), server_default='0', nullable=False))

    # Существующие пользователи заведены вручную — считаем их почту подтверждённой.
    op.execute("UPDATE users SET email_verified_at = now()")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'verification_attempts')
    op.drop_column('users', 'verification_code_expires_at')
    op.drop_column('users', 'verification_code_hash')
    op.drop_column('users', 'email_verified_at')
    op.alter_column('users', 'telegram_id', existing_type=sa.Integer(), nullable=False)
