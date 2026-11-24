"""Облигации с предстоящими событиями (оферта, колл-опцион) по счёту пользователя.

Проверка облигаций не связана со стратегиями: пользователь выбирает любой свой
счёт у брокера. Используется API-роутом /bonds/events; планировщик решает ту же
задачу по расписанию (BOND_EVENTS_MONITOR) — см. src/scheduler/runner.py.
"""
import uuid
from typing import Callable

from starlette.concurrency import run_in_threadpool

from src.core.crypto import decrypt_token
from src.core.instrument_service import InstrumentService
from src.core.user_service import build_portfolio_manager_for_account
from src.db.models.brokers_account import BrokersAccount
from src.models.bond import Bond
from src.services.broker import BrokerAccountNotFoundError


class AccountNotFoundError(Exception):
    """Счёт не найден у пользователя (или помечен удалённым у брокера)."""


class BondService:
    def __init__(self, accounts_repo, portfolio_manager_factory: Callable,
                 instrument_service: InstrumentService,
                 bond_cache_service=None):
        self.accounts_repo = accounts_repo
        self.portfolio_manager_factory = portfolio_manager_factory
        self.instrument_service = instrument_service
        if bond_cache_service is None:
            from src.core.bond_cache_service import MoexBondCacheService

            bond_cache_service = MoexBondCacheService()
        self.bond_cache = bond_cache_service

    async def get_bond_events(self, user, brokers_account_id: uuid.UUID) -> list[Bond]:
        """Облигации с предстоящими событиями на выбранном счёте пользователя."""
        account = await self.accounts_repo.get_for_user(brokers_account_id, user.id)
        if account is None:
            raise AccountNotFoundError(
                f"Account {brokers_account_id} not found for user {user.id}"
            )

        return await self.get_bond_events_for_account(account)

    async def get_bond_events_for_account(self, brokers_account: BrokersAccount) -> list[Bond]:
        """Облигации с предстоящими событиями на уже проверенном на владение счёте."""
        portfolio_manager = build_portfolio_manager_for_account(
            brokers_account, self.portfolio_manager_factory
        )
        users_broker = brokers_account.users_broker
        directory = await self.instrument_service.ensure_directory(
            self.accounts_repo.session,
            decrypt_token(users_broker.broker_token),
            users_broker.sandbox,
            broker=portfolio_manager.broker,
        )

        # Поход к брокеру/MOEX синхронный — уводим в threadpool.
        try:
            moex_bonds = await self.bond_cache.get_bonds(self.accounts_repo.session)
            # Извлекаем брокер из менеджера для переиспользования в refresh
            return await run_in_threadpool(
                portfolio_manager.get_bonds_with_events,
                directory=directory,
                moex_bonds=moex_bonds,
            )
        except BrokerAccountNotFoundError as exc:
            raise AccountNotFoundError(
                f"Account {brokers_account.account_id} not found in broker"
            ) from exc
