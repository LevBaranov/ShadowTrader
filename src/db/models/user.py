from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base
from src.db.enums import AuthProvider
from src.models.notification_channel import NotificationChannel

class User(Base):
    """Пользователь: человек и его данные (стратегии, брокеры, задачи).

    Способы входа (почта, Telegram) вынесены в auth_identities — см. AuthIdentity.
    """

    __tablename__ = 'users'

    # Куда отправлять уведомления планировщика. Пользователь меняет через
    # PATCH /users/me/notifications.
    notification_channel: Mapped[NotificationChannel] = mapped_column(
        default=NotificationChannel.TELEGRAM,
        server_default=NotificationChannel.TELEGRAM.value,
    )

    auth_identities: Mapped[list["AuthIdentity"]] = relationship(
        "AuthIdentity",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    users_broker: Mapped[list["UsersBroker"]] = relationship(
        "UsersBroker",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    users_strategy: Mapped["UsersStrategy"] = relationship(
        "UsersStrategy",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def _identity(self, provider: AuthProvider, verified: bool = True) -> "AuthIdentity | None":
        for identity in self.auth_identities:
            if identity.provider != provider:
                continue
            if verified != (identity.verified_at is not None):
                continue
            return identity
        return None

    @property
    def email(self) -> str | None:
        """Подтверждённая почта пользователя (неподтверждённая — см. pending_email)."""
        identity = self._identity(AuthProvider.EMAIL)
        return identity.external_id if identity else None

    @property
    def pending_email(self) -> str | None:
        """Почта, ожидающая подтверждения кодом (регистрация или смена почты)."""
        identity = self._identity(AuthProvider.EMAIL, verified=False)
        return identity.external_id if identity else None

    @property
    def telegram_id(self) -> int | None:
        identity = self._identity(AuthProvider.TELEGRAM)
        return int(identity.external_id) if identity else None
