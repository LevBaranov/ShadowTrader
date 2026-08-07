import datetime
from typing import List, Tuple, Dict, Optional

from src.core.balancer import Balancer

from src.models.balancer_params import BalancerParams
from src.models.bond import MoexBond, Bond
from src.models.positions import Positions
from src.models.action import Action
from src.models.error import Error
from src.models.index import  Index
from src.models.rebalance import RebalancePreview, PortfolioPosition

from src.services.broker import TBroker, TAccount
from src.services.stock_market import Moex


class PortfolioManager:
    """
    Класс для управления портфелем. Смотрит текущие позиции, анализирует индекс,
    рассчитывает что нужно сделать для балансировки
    """

    def __init__(self, broker_token: str, account_id: str = None, sandbox: bool = None):
        """
        :param broker_token: Токен доступа к брокеру. Резолвится на сервисном слое из БД,
            ядро не знает, откуда он взялся.
        :param account_id: Идентификатор аккаунта пользователя в формате uuid.
        :param sandbox: Режим песочницы. Если None — используется значение по умолчанию из TBroker.
        """
        self.actions: List[Action] = []

        broker_kwargs = {"token": broker_token}
        if sandbox is not None:
            broker_kwargs["sandbox"] = sandbox
        self.broker = TBroker(**broker_kwargs)

        self.account_client: Optional[TAccount] = None
        if account_id:
            self.set_account(account_id)

        self._index_cache: Dict[Tuple[str, datetime.date], Index] = {}
        self.moex = Moex()

    def set_account(self, account_id: str) -> None:
        """
        Установка текущего аккаунта для работы
        :param account_id: Идентификатор аккаунта пользователя в формате uuid
        :return:
        """
        self.account_client = TAccount(account_id, self.broker)
        self.actions = []

    def get_portfolio(self, account_id: str = None) -> Positions:
        """
        Вернуть текущие позиции по аккаунту
        :param account_id: Идентификатор аккаунта пользователя в формате uuid
        :return: Открытые позиции
        """
        if not self.account_client:
            if not account_id:
                raise ValueError("Account client is not initialized and account_id is not provided")
            self.set_account(account_id)
        elif account_id and self.account_client.account_id != account_id:
            self.set_account(account_id)

        return self.account_client.get_positions()

    def get_index_list(self, index_name: str) -> Index:
        """
        Получить список бумаг индекса, кешируя результат на день
        :param index_name: Название индекса
        :return: Состав индекса
        """
        today = datetime.date.today()
        cache_key = (index_name, today)
        if cache_key not in self._index_cache:
            idx = self.moex.get_index_list(index_name)
            self._index_cache[cache_key] = idx
        return self._index_cache[cache_key]

    def execute_actions(self) -> Tuple[List[Action], List[Error]]:
        """
        Выполнить накопленные действия по аккаунту
        :return: Список действий выполненных успешно и список произошедших ошибок
        """
        if not self.account_client:
            raise ValueError("Account client is not initialized")

        success_action_list: List[Action] = []
        error_action_list: List[Error] = []
        for action in self.actions:
            try:
                self.account_client.create_order(action)
                success_action_list.append(action)
            except Error as e:
                error_action_list.append(e)

        return success_action_list, error_action_list

    def get_bonds_with_events(self, account_id: str = None, since: datetime.date = None) -> list[Bond]:
        """
        Возвращает облигации на счёте, по которым впереди есть оферта или колл-опцион.

        * Получаем список всех облигаций у Мосбиржи.
        * Получаем облигации на аккаунте брокера.
        * Оставляем только те бумаги со счёта, у которых есть событие в будущем,
          и прикладываем к каждой список этих событий с датами.
        :param account_id: Идентификатор аккаунта пользователя в формате uuid.
        :param since: С какой даты считать событие предстоящим (по умолчанию — сегодня).
        :return: Список облигаций с предстоящими событиями.
        """
        if not self.account_client:
            if not account_id:
                raise ValueError("Account client is not initialized and account_id is not provided")
            self.set_account(account_id)
        elif account_id and self.account_client.account_id != account_id:
            self.set_account(account_id)

        if since is None:
            since = datetime.date.today()

        moex_bonds: list[MoexBond] = self.moex.get_bonds()
        moex_bonds_by_tickers = {_moex_bond.ticker: _moex_bond for _moex_bond in moex_bonds}
        portfolio_bonds = self.account_client.get_positions().bonds

        bonds_with_events = []
        for _portfolio_bond in portfolio_bonds:
            moex_bond = moex_bonds_by_tickers.get(_portfolio_bond.ticker)
            if moex_bond is None:
                continue

            upcoming = sorted(
                (event for event in moex_bond.events() if event.date >= since),
                key=lambda event: event.date,
            )
            if not upcoming:
                continue

            bonds_with_events.append(
                Bond(
                    uid=_portfolio_bond.uid,
                    figi=_portfolio_bond.figi,
                    ticker=_portfolio_bond.ticker,
                    lot_size=_portfolio_bond.lot_size,
                    type=_portfolio_bond.type,
                    isin=None,
                    offer_date=moex_bond.offer_date,
                    call_option_date=moex_bond.call_option_date,
                    put_option_date=moex_bond.put_option_date,
                    buy_back_price=moex_bond.buy_back_price,
                    short_name=moex_bond.short_name,
                    balance=_portfolio_bond.balance,
                    events=upcoming,
                )
            )

        return bonds_with_events

    def calculate_rebalance(self, index_name: str, params: BalancerParams) -> RebalancePreview:
        """
        Метод для расчёта действий балансировки, кроме действий возвращает данные по весу внутри портфеля и индекса.
        :param index_name: Наименование индекса для расчёта
        :param params: Параметры расчёта — настройки брокера и стратегии.
        :return: Действия, свободные средства и позиции с весом по каждой.
        """

        portfolio = self.get_portfolio()
        portfolio_items = { share.ticker: share for share in portfolio.shares }

        index = self.get_index_list(index_name)
        index_items = { item.ticker: item for item in index.items }

        self.actions = []

        balancer = Balancer(portfolio, index, params)
        actions_list, free_cash = balancer.calculate_actions()

        offers = dict()
        for action in actions_list:
            share = self.broker.find_share(action.get("ticker"), "ticker")
            self.actions.append(Action(type=action.get("type"), quantity=action.get("quantity"), share=share))

            # Знак определяет направление сделки: покупка > 0, продажа < 0.
            quantity = action.get("quantity")
            offers[share.ticker] = -quantity if action.get("type") == "SELL" else quantity


        positions = []

        for position in balancer.calculated_positions:

            portfolio_share = portfolio_items.get( position.ticker )

            index_share = index_items.get( position.ticker )

            uid = ""

            if portfolio_share:
                uid = portfolio_share.uid

            elif index_share:
                found_share = self.broker.find_share( position.ticker,"ticker" )

                uid = found_share.uid

            positions.append(
                PortfolioPosition(
                    uid=uid,
                    ticker=position.ticker,
                    name=(
                        index_share.shortnames
                        if index_share
                        else position.ticker
                    ),
                    index_weight=round(position.target_weight * 100, 2),
                    portfolio_weight=round(position.current_weight * 100, 2),
                    portfolio_count=position.balance,
                    offer=offers.get(position.ticker)
                )
            )

        return RebalancePreview(
            actions=self.actions,
            current_free_cash=portfolio.cash.to_float() if portfolio.cash else 0.0,
            free_cash=free_cash,
            positions=positions
        )
