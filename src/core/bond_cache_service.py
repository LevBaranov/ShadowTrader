import asyncio
import logging
from datetime import timedelta

from src.core.verification import utcnow
from src.db.repositories.moex_bond_repository import MoexBondsRepository
from src.models.bond import MoexBond
from src.services.stock_market import Moex

logger = logging.getLogger(__name__)

CACHE_TTL = timedelta(days=1)


class MoexBondCacheService:
    def __init__(self, moex: Moex | None = None):
        self.moex = moex if moex is not None else Moex()

    async def get_bonds(self, session) -> list[MoexBond]:
        if session is None:
            return []

        repo = MoexBondsRepository(session)
        updated_at = await repo.get_updated_at()
        now = utcnow()
        if updated_at is not None and now - updated_at < CACHE_TTL:
            bonds = await repo.get_all()
            if bonds:
                return bonds

        try:
            await self.refresh(session)
        except Exception:
            logger.exception("Failed to refresh MOEX bonds cache")
        return await repo.get_all()

    async def refresh(self, session) -> int:
        bonds = await asyncio.to_thread(self.moex.get_bonds)
        repo = MoexBondsRepository(session)
        return await repo.replace_all(bonds)
