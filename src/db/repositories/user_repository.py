from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db


    async def get_user_by_telegram_id(self, telegram_id: int) -> User | None:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.db.scalar(stmt)
        return result


    async def create_user(self, telegram_id: int) -> User:

        user = User(telegram_id=telegram_id)

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        return user
