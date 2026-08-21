from datetime import datetime

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from src.db.database import Base


class TelegramLinkRequest(Base):
    """Заявка на привязку Telegram к существующей учётке.

    Создаётся ботом (сервисный ключ), подтверждается пользователем из веба
    по одноразовому коду. Хранится только хеш кода.
    """

    __tablename__ = 'telegram_link_requests'

    # BigInteger: современные telegram id больше 2^31.
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    code_hash: Mapped[str] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
