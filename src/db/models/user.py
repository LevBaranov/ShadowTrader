from sqlalchemy.orm import Mapped, relationship, mapped_column

from src.db.database import Base

class User(Base):

    __tablename__ = 'users'

    telegram_id: Mapped[int] = mapped_column(unique=True)

    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="user",
        cascade="all, delete-orphan"
    )
