import uuid
from typing import List, Dict, Optional
from contextlib import contextmanager
from dataclasses import asdict

from tinkoff.invest import Client, OrderDirection, OrderType, RequestError
from tinkoff.invest.constants import INVEST_GRPC_API_SANDBOX

from src.config import settings
from src.models.account import Account
from src.models.positions import Positions, PositionsShare, PositionsCash, Cash
from src.models.share import Share, ShareList
from src.models.action import Action
from src.models.error import Error

from src.services.utils import cache_data, log_response

class TBroker:
    """
    Класс брокера Т-Банка. Будем получать информацию об аккаунтах
    """

    def __init__(self, token: str = settings.broker.token, sandbox: bool = settings.broker.sandbox_mode):
        self.token = token
        self.target = INVEST_GRPC_API_SANDBOX if sandbox else None
        self._shares_by_uid: Dict[str, Share] = {}
        self._shares_by_ticker: Dict[str, Share] = {}

    @contextmanager
    def get_client(self):
        """Контекстный менеджер для работы с клиентом."""
        params = {"token": self.token}
        if self.target:
            params["target"] = self.target

        with Client(**params) as client:
            yield client

    def get_all_accounts(self) -> List[Account]:
        """
            Возвращает список всех аккаунтов доступных в брокере
        :return: List[Account]
        """
        with self.get_client() as client:
            accounts = client.users.get_accounts().accounts

        return [Account(id=a.id, name=a.name) for a in accounts]

    @log_response()
    @cache_data(ttl_seconds=86400)
    def get_all_shares(self) -> ShareList:
        """
        Возвращает список акций с их дополнительной информацией.
        :return: ShareList
        """
        shares = []
        with self.get_client() as client:
            instruments = client.instruments
            shares = [
                Share(f.uid, f.figi, f.ticker, f.lot, f.isin)
                for f in instruments.shares().instruments if f.currency == 'rub'
            ]
            for share in shares:
                self._shares_by_uid[share.uid] = share
                self._shares_by_ticker[share.ticker] = share

        return ShareList(shares)


    @log_response()
    def find_share(self, value: str, field: str = "uid") -> Optional[Share]:
        """
        Метод для поиска информации об акции. Может принимать на вход uid или ticker
        :param value: Значение, по которому осуществляется поиск.
        :param field: Тип значения, по которому ищем. Допустимые значения: uid, ticker.
        :return: Share. Информация об акции
        """
        lookup_maps = {
            "ticker": self._shares_by_ticker,
            "uid": self._shares_by_uid
        }
        result = lookup_maps.get(field, {}).get(value)
        if not result:
            self.get_all_shares()
            # пересоздаём lookup_maps, так как словари могли обновиться
            lookup_maps = {
                "ticker": self._shares_by_ticker,
                "uid": self._shares_by_uid
            }
            result = lookup_maps.get(field, {}).get(value)

        return result


class TAccount:
    """
    Класс аккаунта со стороны Тбанка. Реализует получение позиций в аккаунте,
    создание заявок.
    """
    def __init__(self, account_id: str, broker: TBroker):
        self.account_id = account_id
        self.broker = broker

    def get_positions(self)-> Positions:
        """
        Возвращает позиции на счете.
        """

        with self.broker.get_client() as client:
            positions = client.operations.get_positions(account_id=self.account_id)

            if not positions.securities:
                return Positions(cash=PositionsCash(**asdict(positions.money[0])) if positions.money else None,
                                 shares=[])

            # Матчим акции и баланс
            instrument_uids = []
            share_balance = []
            for position in positions.securities:
                share = self.broker.find_share(position.instrument_uid)
                instrument_uids.append(position.instrument_uid)
                if share: # Проблема с BBG007N0Z367. Его нет в списке всех акций, но в портфеле он остался, хоть и продан
                    share_balance.append((share, position.balance))

            # Получаем информацию о последних ценах
            last_prices = {
                last_price.instrument_uid: last_price.price
                for last_price in client.market_data.get_last_prices(
                    instrument_id=[p.instrument_uid for p in positions.securities]).last_prices
            }
            shares_positions = []
            for share, balance in share_balance:
                shares_positions.append(
                    PositionsShare(
                        share_uid=share.uid,
                        figi=share.figi,
                        balance=balance,
                        last_price=Cash(**asdict(last_prices.get(share.uid))),
                        lot_size=share.lot_size,
                        ticker=share.ticker
                    )
                )
        return Positions(
            cash=PositionsCash(**asdict(positions.money[0])) if positions.money else None,
            shares=shares_positions
        )

    def create_order(self, action: Action):
        """
        Создаёт ордер у брокера в аккаунте.
        :param action: Данные для ордера
        :return:
        """
        type_order = OrderDirection.ORDER_DIRECTION_BUY if action.type == "BUY" else OrderDirection.ORDER_DIRECTION_SELL
        order_id = str(uuid.uuid4())
        with self.broker.get_client() as client:
            try:
                return client.orders.post_order(
                    instrument_id=action.share.uid,
                    quantity=action.quantity,
                    # price=price,
                    direction=type_order,
                    account_id=self.account_id,
                    order_type=OrderType.ORDER_TYPE_BESTPRICE,  # TODO: Добавить другие типы
                    order_id=order_id
                )
            except RequestError as e:
                raise Error(source="Broker", source_data=e, data=action, description=e.metadata.message)



if __name__ == "__main__":
    import pprint


    br = TBroker()
    print(br.find_share("SBER", "ticker"))
    pprint.pprint(br.get_all_shares())
    accs = br.get_all_accounts()
    print(accs)

    ac = TAccount(accs[0].id, br)
    pos = ac.get_positions()
    print(pos)