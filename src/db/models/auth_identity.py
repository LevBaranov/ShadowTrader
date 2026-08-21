import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base
from src.db.enums import AuthProvider


class AuthIdentity(Base):
    """Способ входа пользователя.

    Один пользователь может иметь несколько способов входа (почта, Telegram, ...);
    все поля аутентификации живут здесь, а users — это «человек и его данные».
    """

    __tablename__ = 'auth_identities'
    __table_args__ = (
        UniqueConstraint('provider', 'external_id'),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    provider: Mapped[AuthProvider] = mapped_column(nullable=False)
    # EMAIL: почта в нижнем регистре; TELEGRAM: telegram_id строкой.
    external_id: Mapped[str] = mapped_column(nullable=False)

    # Только для EMAIL.
    password_hash: Mapped[str | None]

    # EMAIL: момент подтверждения почты; TELEGRAM: заполняется сразу при создании
    # (владение чатом подтверждено самим фактом диалога).
    verified_at: Mapped[datetime | None]
    verification_code_hash: Mapped[str | None]
    verification_code_expires_at: Mapped[datetime | None]
    verification_attempts: Mapped[int] = mapped_column(default=0, server_default="0")

    user: Mapped["User"] = relationship(
        "User",
        back_populates="auth_identities",
        lazy="selectin",
    )
