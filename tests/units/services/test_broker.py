import pytest
from unittest.mock import MagicMock, patch

import os
import json

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_data")


class TestTBroker:

    @staticmethod
    def load_test_data(filename):
        with open(os.path.join(TEST_DATA_DIR, filename), "r") as f:
            return json.load(f)

    def test_init_sandbox(self):
        from t_tech.invest.constants import INVEST_GRPC_API_SANDBOX
        from src.services.broker import TBroker

        broker = TBroker(token="test-token", sandbox=True)

        assert broker.token == "test-token"
        assert broker.target == INVEST_GRPC_API_SANDBOX
        assert broker._shares_by_uid == {}
        assert broker._shares_by_ticker == {}

    def test_init_production(self):
        from src.services.broker import TBroker

        broker = TBroker(token="test-token", sandbox=False)

        assert broker.token == "test-token"
        assert broker.target is None

    def test_get_all_accounts(self):
        from src.models.account import Account
        from src.services.broker import TBroker

        mock_client = MagicMock()
        mock_client.__enter__.return_value.users.get_accounts.return_value.accounts = [
            MagicMock(id="acc_1", name="Test Account 1"),
            MagicMock(id="acc_2", name="Test Account 2"),
        ]

        with patch("src.services.broker.Client", return_value=mock_client):
            mock_broker = TBroker(token="test-token", sandbox=True)
            accounts = mock_broker.get_all_accounts()
            assert isinstance(accounts, list)
            assert len(accounts) == 2
            for account in accounts:
                assert isinstance(account, Account)
                assert hasattr(account, 'id')
                assert hasattr(account, 'name')


    @pytest.mark.parametrize("mock_data",
                             load_test_data("broker_find_share_response_success.json")
                             )
    def test_find_share_triggers_cache(self, mock_data, monkeypatch):

        from src.services.broker import TBroker
        from src.models.share import Share

        response = mock_data.get("response")
        request = mock_data.get("request")
        mock_instrument = MagicMock()
        mock_instrument.uid = response.get("uid")
        mock_instrument.figi = response.get("figi")
        mock_instrument.ticker = response.get("ticker")
        mock_instrument.lot = response.get("lot_size")
        mock_instrument.isin = response.get("isin")
        mock_instrument.currency = "rub"

        def make_mock_client():
            mock_client = MagicMock()
            mock_client.instruments.shares.return_value.instruments = [mock_instrument]
            return mock_client

        def make_mock_context_manager(*args, **kwargs):
            mock_context_manager = MagicMock()
            mock_context_manager.__enter__.return_value = make_mock_client()
            mock_context_manager.__exit__.return_value = None
            return mock_context_manager

        with patch("src.services.broker.Client", side_effect=make_mock_context_manager):
            mock_broker = TBroker(token="test-token", sandbox=True)

            share = mock_broker.find_share(value=request.get("value"), field=request.get("field"))

            assert isinstance(share, Share)

    def test_find_share_uses_directory_without_network(self):
        from src.services.broker import TBroker
        from src.models.instrument_directory import InstrumentDirectory, InstrumentMeta
        from src.models.share import Share

        broker = TBroker(token="test-token", sandbox=True)
        directory = InstrumentDirectory(
            sandbox=True,
            updated_at=None,
            by_ticker={
                "SBER": InstrumentMeta(
                    uid="uid-1", ticker="SBER", figi="figi",
                    isin="isin", lot_size=10, type="share",
                )
            },
        )

        with patch("src.services.broker.Client") as mock_client_cls:
            share = broker.find_share("SBER", "ticker", directory=directory)

            assert isinstance(share, Share)
            assert share.uid == "uid-1"
            assert share.lot_size == 10
            mock_client_cls.assert_not_called()

    def test_find_share_directory_miss_uses_cache(self):
        from src.services.broker import TBroker
        from src.models.instrument_directory import InstrumentDirectory
        from src.models.share import Share

        broker = TBroker(token="test-token", sandbox=True)
        broker._shares_by_ticker["SBER"] = Share("uid-1", "figi", "SBER", 10, "isin", "share")
        directory = InstrumentDirectory(sandbox=True, updated_at=None)

        share = broker.find_share("SBER", "ticker", directory=directory)

        assert share.uid == "uid-1"

    def test_find_share_directory_miss_does_not_hit_network(self):
        from src.services.broker import TBroker
        from src.models.instrument_directory import InstrumentDirectory

        broker = TBroker(token="test-token", sandbox=True)
        directory = InstrumentDirectory(sandbox=True, updated_at=None)

        with patch("src.services.broker.Client") as mock_client_cls:
            share = broker.find_share("MISSING", "ticker", directory=directory)

        assert share is None
        mock_client_cls.assert_not_called()

    def test_find_share_without_directory_refreshes_once(self):
        from src.services.broker import TBroker
        from src.models.share import ShareList

        broker = TBroker(token="test-token", sandbox=True)
        calls = []

        def fake_get_all_shares():
            calls.append(1)
            broker._shares_refreshed = True
            return ShareList([])

        broker.get_all_shares = fake_get_all_shares

        assert broker.find_share("NOPE1", "ticker") is None
        assert broker.find_share("NOPE2", "ticker") is None
        assert len(calls) == 1

    def test_find_instrument_uses_directory(self):
        from src.services.broker import TBroker
        from src.models.instrument_directory import InstrumentDirectory, InstrumentMeta
        from src.models.instrument import InstrumentBase

        broker = TBroker(token="test-token", sandbox=True)
        directory = InstrumentDirectory(
            sandbox=True,
            updated_at=None,
            by_uid={
                "uid-9": InstrumentMeta(
                    uid="uid-9", ticker="BOND1", figi="figi",
                    isin="isin", lot_size=1, type="bond",
                )
            },
        )

        with patch("src.services.broker.Client") as mock_client_cls:
            instrument = broker.find_instrument("uid-9", "uid", directory=directory)

            assert isinstance(instrument, InstrumentBase)
            assert instrument.ticker == "BOND1"
            mock_client_cls.assert_not_called()

class TestTAccount:

    def test_get_positions_with_securities_and_money(self):
        from src.services.broker import TAccount
        from src.models.share import Share
        from src.models.positions import Positions, Cash, PositionsCash

        broker = MagicMock()
        client = MagicMock()

        # Мокаем данные
        position_security = MagicMock(instrument_uid="uid123", balance=5, instrument_type="share")
        share = Share(uid="uid123", figi="figi123", ticker="TST", lot_size=10, isin="ISIN123", type="share")

        last_price = MagicMock(instrument_uid="uid123", price=Cash(units=100, nano=0))
        money = [PositionsCash(currency="rub", units=1000, nano=0)]

        # Настраиваем клиент
        client.operations.get_positions.return_value = MagicMock(securities=[position_security], money=money)
        client.market_data.get_last_prices.return_value.last_prices = [last_price]

        broker.get_client.return_value.__enter__.return_value = client
        broker.find_instrument.return_value = share

        account = TAccount(account_id="acc_1", broker=broker)
        positions = account.get_positions(None)

        assert isinstance(positions, Positions)
        assert positions.cash.currency == "rub"
        assert len(positions.shares) == 1
        assert positions.shares[0].ticker == "TST"

    def test_get_positions_resolves_from_directory(self):
        """Held-бумаги резолвятся из directory: find_instrument живьём не вызывается."""
        from src.services.broker import TAccount, TBroker
        from src.models.instrument_directory import InstrumentDirectory, InstrumentMeta
        from src.models.positions import Positions, Cash, PositionsCash

        broker = TBroker(token="test-token", sandbox=True)
        client = MagicMock()

        position_security = MagicMock(instrument_uid="uid123", balance=5, instrument_type="share")
        last_price = MagicMock(instrument_uid="uid123", price=Cash(units=100, nano=0))
        money = [PositionsCash(currency="rub", units=1000, nano=0)]

        client.operations.get_positions.return_value = MagicMock(securities=[position_security], money=money)
        client.market_data.get_last_prices.return_value.last_prices = [last_price]

        broker.get_client = MagicMock(return_value=client)
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)

        directory = InstrumentDirectory(
            sandbox=True,
            updated_at=None,
            by_uid={
                "uid123": InstrumentMeta(
                    uid="uid123", ticker="TST", figi="figi123",
                    isin="ISIN123", lot_size=10, type="share",
                )
            },
        )

        with patch("src.services.broker.Client") as mock_client_cls:
            # get_client замокано выше — Client для инструментов не используется.
            account = TAccount(account_id="acc_1", broker=broker)
            positions = account.get_positions(directory=directory)

        assert isinstance(positions, Positions)
        assert len(positions.shares) == 1
        assert positions.shares[0].ticker == "TST"
        assert positions.shares[0].lot_size == 10
        mock_client_cls.assert_not_called()

    def test_get_positions_with_only_money(self):
        from src.services.broker import TAccount
        from src.models.positions import Positions, PositionsCash

        broker = MagicMock()
        client = MagicMock()

        money = [PositionsCash(currency="usd", units=200, nano=0)]

        client.operations.get_positions.return_value = MagicMock(securities=[], money=money)
        broker.get_client.return_value.__enter__.return_value = client

        account = TAccount(account_id="acc_2", broker=broker)
        positions = account.get_positions(None)

        assert isinstance(positions, Positions)
        assert positions.cash.currency == "usd"
        assert positions.shares == []

    def test_get_positions_empty(self):
        from src.services.broker import TAccount
        from src.models.positions import Positions

        broker = MagicMock()
        client = MagicMock()

        client.operations.get_positions.return_value = MagicMock(securities=[], money=[])
        broker.get_client.return_value.__enter__.return_value = client

        account = TAccount(account_id="acc_3", broker=broker)
        positions = account.get_positions(None)

        assert isinstance(positions, Positions)
        assert positions.cash is None
        assert positions.shares == []

    def test_get_positions_account_not_found(self):
        from grpc import StatusCode
        from t_tech.invest import RequestError
        from src.services.broker import TAccount, BrokerAccountNotFoundError

        broker = MagicMock()
        client = MagicMock()

        error = RequestError(StatusCode.NOT_FOUND, "50004", MagicMock(message="Account not found"))
        client.operations.get_positions.side_effect = error
        broker.get_client.return_value.__enter__.return_value = client

        account = TAccount(account_id="acc_gone", broker=broker)

        with pytest.raises(BrokerAccountNotFoundError):
            account.get_positions(None)

    def test_get_positions_other_request_error_reraised(self):
        from grpc import StatusCode
        from t_tech.invest import RequestError
        from src.services.broker import TAccount

        broker = MagicMock()
        client = MagicMock()

        error = RequestError(StatusCode.INTERNAL, "50000", MagicMock(message="Internal error"))
        client.operations.get_positions.side_effect = error
        broker.get_client.return_value.__enter__.return_value = client

        account = TAccount(account_id="acc_6", broker=broker)

        with pytest.raises(RequestError):
            account.get_positions(None)

    def test_create_order_buy(self):
        from src.services.broker import TAccount
        from src.models.action import Action
        from t_tech.invest.grpc import OrderDirection

        broker = MagicMock()
        client = MagicMock()

        broker.get_client.return_value.__enter__.return_value = client
        action = Action(type="BUY", share=MagicMock(uid="uid123"), quantity=10)

        account = TAccount(account_id="acc_4", broker=broker)
        response = account.create_order(action)

        # create_order передаёт один объект PostOrderRequest
        client.orders.post_order.assert_called_once()
        args, kwargs = client.orders.post_order.call_args
        request = args[0] if args else kwargs["request"]
        assert request.direction == OrderDirection.ORDER_DIRECTION_BUY
        assert request.instrument_id == "uid123"
        assert request.quantity == 10
        assert request.account_id == "acc_4"

    def test_create_order_error(self):
        from src.services.broker import TAccount
        from src.models.action import Action
        from t_tech.invest import RequestError

        broker = MagicMock()
        client = MagicMock()

        error = RequestError("Error", metadata=MagicMock(message="Order failed"), details="Order failed")
        client.orders.post_order.side_effect = error
        broker.get_client.return_value.__enter__.return_value = client

        action = Action(type="SELL", share=MagicMock(uid="uid123"), quantity=1)
        account = TAccount(account_id="acc_5", broker=broker)

        with pytest.raises(Exception) as exc:
            account.create_order(action)

        assert "Order failed" in str(exc.value)