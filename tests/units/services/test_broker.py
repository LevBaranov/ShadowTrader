import pytest
from unittest.mock import MagicMock, patch

import os
import json

class TestTBroker:

    @staticmethod
    def load_test_data(filename):
        with open(os.path.join("test_data", filename), "r") as f:
            return json.load(f)

    @pytest.fixture(autouse=True)
    def disable_cache(self, monkeypatch):
        """Фикстура для отключения кэширования во всех тестах класса"""

        def no_cache_decorator(ttl_seconds):
            def decorator(func):
                return func

            return decorator

        # Подменяем ДО любого импорта TBroker
        monkeypatch.setattr("src.services.utils.cache_data", no_cache_decorator)

    def test_init_with_default_settings(self):
        from src.config import settings
        from tinkoff.invest.constants import INVEST_GRPC_API_SANDBOX
        from src.services.broker import TBroker

        broker = TBroker()

        assert broker.token == settings.broker.token
        assert broker.target == (INVEST_GRPC_API_SANDBOX if settings.broker.sandbox_mode else None)
        assert broker._shares_by_uid == {}
        assert broker._shares_by_ticker == {}

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

class TestTAccount:

    def test_get_positions_with_securities_and_money(self):
        from src.services.broker import TAccount
        from src.models.share import Share
        from src.models.positions import Positions, Cash, PositionsCash

        broker = MagicMock()
        client = MagicMock()

        # Мокаем данные
        position_security = MagicMock(instrument_uid="uid123", balance=5)
        share = Share(uid="uid123", figi="figi123", ticker="TST", lot_size=10, isin="ISIN123")

        last_price = MagicMock(instrument_uid="uid123", price=Cash(units=100, nano=0))
        money = [PositionsCash(currency="rub", units=1000, nano=0)]

        # Настраиваем клиент
        client.operations.get_positions.return_value = MagicMock(securities=[position_security], money=money)
        client.market_data.get_last_prices.return_value.last_prices = [last_price]

        broker.get_client.return_value.__enter__.return_value = client
        broker.find_share.return_value = share

        account = TAccount(account_id="acc_1", broker=broker)
        positions = account.get_positions()

        assert isinstance(positions, Positions)
        assert positions.cash.currency == "rub"
        assert len(positions.shares) == 1
        assert positions.shares[0].ticker == "TST"

    def test_get_positions_with_only_money(self):
        from src.services.broker import TAccount
        from src.models.positions import Positions, PositionsCash

        broker = MagicMock()
        client = MagicMock()

        money = [PositionsCash(currency="usd", units=200, nano=0)]

        client.operations.get_positions.return_value = MagicMock(securities=[], money=money)
        broker.get_client.return_value.__enter__.return_value = client

        account = TAccount(account_id="acc_2", broker=broker)
        positions = account.get_positions()

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
        positions = account.get_positions()

        assert isinstance(positions, Positions)
        assert positions.cash is None
        assert positions.shares == []

    def test_create_order_buy(self):
        from src.services.broker import TAccount
        from src.models.action import Action
        from tinkoff.invest import OrderDirection

        broker = MagicMock()
        client = MagicMock()

        broker.get_client.return_value.__enter__.return_value = client
        action = Action(type="BUY", share=MagicMock(uid="uid123"), quantity=10)

        account = TAccount(account_id="acc_4", broker=broker)
        response = account.create_order(action)

        client.orders.post_order.assert_called_once()
        args, kwargs = client.orders.post_order.call_args
        assert kwargs["direction"] == OrderDirection.ORDER_DIRECTION_BUY
        assert kwargs["instrument_id"] == "uid123"
        assert kwargs["quantity"] == 10
        assert kwargs["account_id"] == "acc_4"

    def test_create_order_error(self):
        from src.services.broker import TAccount
        from src.models.action import Action
        from tinkoff.invest import RequestError

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