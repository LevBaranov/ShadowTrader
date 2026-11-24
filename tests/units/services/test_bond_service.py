"""Тесты сервиса облигаций: проверка идёт по счёту пользователя, не по стратегии."""
import asyncio
import uuid
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from src.core.bond_service import AccountNotFoundError, BondService
from src.models.bond import BondEvent, BondEventType


class FakeAccountRepo:
    session = None

    def __init__(self, account=None, owner_id=None):
        self.account = account
        self.owner_id = owner_id
        self.calls = []

    async def get_for_user(self, account_pk, user_id):
        self.calls.append((account_pk, user_id))
        if self.account is not None and account_pk == self.account.id and user_id == self.owner_id:
            return self.account
        return None


class FakeManager:
    def __init__(self, bonds):
        self.bonds = bonds
        self.broker = None

    def get_bonds_with_events(self, account_id=None, since=None, directory=None, moex_bonds=None):
        return self.bonds


class FakeInstrumentService:
    async def ensure_directory(self, session, token, sandbox, must_contain=frozenset(), broker=None):
        from src.models.instrument_directory import InstrumentDirectory
        return InstrumentDirectory(sandbox=sandbox, updated_at=None)


def make_account(owner_token="t.token"):
    from src.core.crypto import encrypt_token
    return SimpleNamespace(
        id=uuid.uuid4(),
        users_broker=SimpleNamespace(
            broker_token=encrypt_token(owner_token),
            sandbox=False,
        ),
    )


@pytest.fixture
def user():
    return SimpleNamespace(id=uuid.uuid4())


@pytest.fixture
def bonds():
    return [
        SimpleNamespace(
            ticker="RU01",
            events=[BondEvent(type=BondEventType.OFFER, date=date.today() + timedelta(days=30))],
        )
    ]


def make_service(monkeypatch, account_repo, bonds):
    service = BondService(
        accounts_repo=account_repo,
        portfolio_manager_factory=None,
        instrument_service=FakeInstrumentService(),
    )
    monkeypatch.setattr(
        "src.core.bond_service.build_portfolio_manager_for_account",
        lambda account, factory: FakeManager(bonds),
    )
    return service


def test_returns_bonds_for_own_account(user, bonds, monkeypatch):
    account = make_account()
    repo = FakeAccountRepo(account, owner_id=user.id)
    service = make_service(monkeypatch, repo, bonds)

    result = asyncio.run(service.get_bond_events(user, account.id))

    assert result == bonds
    assert repo.calls == [(account.id, user.id)]


def test_foreign_account_raises(user, bonds, monkeypatch):
    account = SimpleNamespace(id=uuid.uuid4())
    # Счёт есть, но принадлежит другому пользователю.
    repo = FakeAccountRepo(account, owner_id=uuid.uuid4())
    service = make_service(monkeypatch, repo, bonds)

    with pytest.raises(AccountNotFoundError):
        asyncio.run(service.get_bond_events(user, account.id))


def test_unknown_account_raises(user, bonds, monkeypatch):
    repo = FakeAccountRepo(None)
    service = make_service(monkeypatch, repo, bonds)

    with pytest.raises(AccountNotFoundError):
        asyncio.run(service.get_bond_events(user, uuid.uuid4()))


def test_any_account_is_allowed_without_strategy(user, bonds, monkeypatch):
    """Проверка облигаций не требует стратегии на счёте."""
    account = make_account()
    account.users_strategy = None
    repo = FakeAccountRepo(account, owner_id=user.id)
    service = make_service(monkeypatch, repo, bonds)

    assert asyncio.run(service.get_bond_events(user, account.id)) == bonds
