import uuid
from typing import List, Dict, Optional
from contextlib import contextmanager
from dataclasses import asdict

from grpc import StatusCode
from t_tech.invest import RequestError
from t_tech.invest.exceptions import UnauthenticatedError
from t_tech.invest.grpc import Client, OrderDirection, OrderType
from t_tech.invest.grpc import PositionsRequest, GetLastPricesRequest, PostOrderRequest
from t_tech.invest.constants import INVEST_GRPC_API_SANDBOX

from src.models.instrument import InstrumentBase

from src.logging_setup import integration_call

from src.models.account import Account
from src.models.positions import Positions, PositionsCash, Cash, PositionsInstrument
from src.models.share import Share, ShareList
from src.models.action import Action
from src.models.error import Error


class BrokerAuthError(Exception):
    """Токен брокера отсутствует или недействителен."""


class BrokerAccountNotFoundError(Exception):
    """Счёт не найден у брокера: удалён/закрыт на его стороне, но ещё числится у нас."""


# Имя интеграции в логах: пишется в logs/broker.log.
SERVICE = "broker"


class TBroker:
    """
    Класс брокера Т-Банка. Будем получать информацию об аккаунтах
    """

    def __init__(self, token: str, sandbox: bool):
        self.token = token
        self.target = INVEST_GRPC_API_SANDBOX if sandbox else None
        self._shares_by_uid: Dict[str, Share] = {}
        self._shares_by_ticker: Dict[str, Share] = {}
        self._instruments_by_uid: Dict[str, InstrumentBase] = {}
        self._instruments_by_ticker: Dict[str, InstrumentBase] = {}

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
        with integration_call(SERVICE, "get_accounts", sandbox=bool(self.target)) as call:
            try:
                with self.get_client() as client:
                    accounts = client.users.get_accounts().accounts
            except UnauthenticatedError as exc:
                raise BrokerAuthError("Broker token is invalid") from exc

            result = [Account(id=a.id, name=a.name) for a in accounts]
            call.add(count=len(result))
            call.detail(accounts=[a.id for a in result])

            return result

    def get_all_shares(self) -> ShareList:
        """
        Возвращает список акций с их дополнительной информацией.
        :return: ShareList
        """
        with integration_call(SERVICE, "get_all_shares") as call:
            with self.get_client() as client:
                instruments = client.instruments
                shares = [
                    Share(f.uid, f.figi, f.ticker, f.lot, f.isin, "share")
                    for f in instruments.shares().instruments if f.currency == 'rub'
                ]
                for share in shares:
                    self._shares_by_uid[share.uid] = share
                    self._shares_by_ticker[share.ticker] = share

            call.add(count=len(shares))
            call.detail(tickers=[share.ticker for share in shares])

            return ShareList(shares)

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

    def find_instrument(self, value: str, field: str = "uid") -> Optional[InstrumentBase]:
        """
        Метод для поиска информации об облигациях. Может принимать на вход uid или ticker
        :param value: Значение, по которому осуществляется поиск.
        :param field: Тип значения, по которому ищем. Допустимые значения: uid, ticker.
        :return: Bond. Информация об облигации
        """
        def _find(_value: str, _field: str = "uid"):

            lookup_maps = {
                "ticker": self._instruments_by_ticker,
                "uid": self._instruments_by_uid
            }
            return lookup_maps.get(_field, {}).get(_value)

        result = _find(value, field)
        if not result:
            self.get_all_instruments()
            # пересоздаём lookup_maps, так как словари могли обновиться
            result = _find(value, field)

        return result

    def get_all_instruments(self) -> list[InstrumentBase]:
        """
        Возвращает список всех инструментов с их дополнительной информацией.
        :return: Список инструментов с их базовой информацией
        """
        with integration_call(SERVICE, "get_all_instruments") as call:
            all_instruments = []
            bonds_count = 0
            with self.get_client() as client:
                broker_instruments = client.instruments

                for _i in broker_instruments.bonds().instruments:
                    if _i.currency == 'rub':
                        instrument = InstrumentBase(_i.uid, _i.figi, _i.ticker, _i.lot, _i.isin, "bond")
                        self._instruments_by_uid[instrument.uid] = instrument
                        self._instruments_by_ticker[instrument.ticker] = instrument

                        all_instruments.append(instrument)
                        bonds_count += 1

                for _i in broker_instruments.shares().instruments:
                    if _i.currency == 'rub':
                        instrument = InstrumentBase(_i.uid, _i.figi, _i.ticker, _i.lot, _i.isin, "share")
                        self._instruments_by_uid[instrument.uid] = instrument
                        self._instruments_by_ticker[instrument.ticker] = instrument

                        all_instruments.append(instrument)

            call.add(bonds=bonds_count, shares=len(all_instruments) - bonds_count)
            call.detail(tickers=[instrument.ticker for instrument in all_instruments])

            return all_instruments



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
        def create_position_instrument(_i:InstrumentBase, _b:int, _last_price) -> PositionsInstrument:

            return PositionsInstrument(
                            uid=_i.uid,
                            figi=_i.figi,
                            balance=_b,
                            last_price=Cash(**asdict(_last_price)),
                            lot_size=_i.lot_size,
                            ticker=_i.ticker,
                            type=_i.type
                        )


        with integration_call(SERVICE, "get_positions", account=self.account_id) as call:
            with self.broker.get_client() as client:
                request = PositionsRequest(account_id=self.account_id)
                try:
                    positions = client.operations.get_positions(request)
                except RequestError as e:
                    if e.code == StatusCode.NOT_FOUND:
                        raise BrokerAccountNotFoundError(
                            f"Account {self.account_id} not found in broker"
                        ) from e
                    raise

                if not positions.securities:
                    call.add(securities=0)
                    return Positions(cash=PositionsCash(**asdict(positions.money[0])) if positions.money else None,
                                     shares=[])

                # Матчим акции и баланс
                instrument_uids = []
                instrument_balance = []
                for _position in positions.securities:
                    if _position.instrument_type in ["share", "bond"]:
                        instrument_uids.append(_position.instrument_uid)
                        instrument = self.broker.find_instrument(_position.instrument_uid)

                        # TODO: Возможно логика лишняя и требует удаления
                        if instrument:  # Проблема с BBG007N0Z367. Его нет в списке всех акций, но в портфеле он остался, хоть и продан
                            instrument_balance.append((instrument, _position.balance))

                # Получаем информацию о последних ценах
                last_prices = {
                    last_price.instrument_uid: last_price.price
                    for last_price in client.market_data.get_last_prices(
                        GetLastPricesRequest(instrument_id=[p.instrument_uid for p in positions.securities])
                    ).last_prices
                }

                shares_positions = []
                bonds_positions = []
                for _instrument, _balance in instrument_balance:
                    if _instrument.type == "share":
                        shares_positions.append(
                            create_position_instrument(_instrument, _balance, last_prices.get(_instrument.uid))
                        )
                    if _instrument.type == "bond":
                        bonds_positions.append(
                            create_position_instrument(_instrument, _balance, last_prices.get(_instrument.uid))
                        )

            result = Positions(
                cash=PositionsCash(**asdict(positions.money[0])) if positions.money else None,
                shares=shares_positions,
                bonds=bonds_positions
            )

            call.add(shares=len(shares_positions), bonds=len(bonds_positions))
            call.detail(positions=asdict(result))

            return result

    def create_order(self, action: Action):
        """
        Создаёт ордер у брокера в аккаунте.
        :param action: Данные для ордера
        :return:
        """
        type_order = OrderDirection.ORDER_DIRECTION_BUY if action.type == "BUY" else OrderDirection.ORDER_DIRECTION_SELL
        order_id = str(uuid.uuid4())

        with integration_call(
                SERVICE, "create_order",
                account=self.account_id,
                ticker=action.share.ticker,
                type=action.type,
                quantity=action.quantity,
                order_id=order_id,
        ) as call:
            with self.broker.get_client() as client:
                try:
                    request = PostOrderRequest(
                        instrument_id=action.share.uid,
                        quantity=action.quantity,
                        # price=price,
                        direction=type_order,
                        account_id=self.account_id,
                        order_type=OrderType.ORDER_TYPE_BESTPRICE,  # TODO: Добавить другие типы
                        order_id=order_id
                    )
                    response = client.orders.post_order(request)

                except RequestError as e:
                    raise Error(source="Broker", source_data=e, data=action, description=e.metadata.message)

                call.detail(response=str(response))

                return response

