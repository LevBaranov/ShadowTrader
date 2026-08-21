from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.telegram_link_request import TelegramLinkRequest


class TelegramLinkRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_telegram_id(self, telegram_id: int) -> TelegramLinkRequest | None:
        stmt = select(TelegramLinkRequest).where(
            TelegramLinkRequest.telegram_id == telegram_id
        )
        return await self.db.scalar(stmt)

    async def get_by_code_hash(self, code_hash: str) -> TelegramLinkRequest | None:
        stmt = select(TelegramLinkRequest).where(
            TelegramLinkRequest.code_hash == code_hash
        )
        return await self.db.scalar(stmt)

    async def create(
            self, telegram_id: int, code_hash: str, expires_at: datetime
    ) -> TelegramLinkRequest:
        request = TelegramLinkRequest(
            telegram_id=telegram_id,
            code_hash=code_hash,
            expires_at=expires_at,
        )

        self.db.add(request)
        await self.db.commit()
        await self.db.refresh(request)

        return request

    async def delete(self, request: TelegramLinkRequest) -> None:
        await self.db.delete(request)
        await self.db.commit()

    async def save(self) -> None:
        await self.db.commit()
