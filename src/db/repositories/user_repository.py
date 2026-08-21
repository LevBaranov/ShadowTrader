from sqlalchemy.ext.asyncio import AsyncSession

# Поиск/создание пользователей по способам входа — в AuthIdentityRepository:
# у пользователя больше нет собственных полей аутентификации.


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save(self) -> None:
        """Зафиксировать изменения в загруженных сущностях."""
        await self.db.commit()
