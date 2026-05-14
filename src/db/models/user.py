from sqlalchemy.orm import Mapped, relationship, mapped_column

from src.db.database import Base

class User(Base):

    __tablename__ = 'users'

    telegram_id: Mapped[int] = mapped_column(unique=True)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(nullable=False)

    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="user",
        cascade="all, delete-orphan"
    )
