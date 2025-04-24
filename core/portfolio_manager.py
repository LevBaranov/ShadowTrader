import datetime
from typing import List, Tuple, Dict, Optional

from models.action import Action
from models.positions import Positions
from models.account import Account
from models.index import Index
from models.error import Error

from services.broker import TBroker, TAccount
from services.stock_market import Moex

from balancer import Balancer


class PortfolioManager:
    """
    Класс для управления портфелем. Смотрит текущие позиции, анализирует индекс,
    рассчитывает что нужно сделать для балансировки
    """

    def __init__(self):
        self.actions: List[Action] = []
        self.broker = TBroker()
        self.account_client: Optional[TAccount] = None
        self._index_cache: Dict[Tuple[str, datetime.date], Index] = {}
        self.moex = Moex()

    def get_user_accounts(self) -> List[Account]:
        """
        Получить список всех доступных пользователю аккаунтов
        :return: Список аккаунтов
        """
        return self.broker.get_all_accounts()

    def set_account(self, account: Account) -> None:
        """
        Установка текущего аккаунта для работы
        :param account: Аккаунт пользователя
        :return:
        """
        self.account_client = TAccount(account.id, self.broker)
        self.actions = []

    def get_portfolio(self, account: Account) -> Positions:
        """
        Вернуть текущие позиции по аккаунту
        :param account: Аккаунт пользователя
        :return: Открытые позиции
        """
        if not self.account_client or self.account_client.account_id != account.id:
            self.set_account(account)
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

    def get_action_for_rebalance(self, portfolio: Positions, index: Index)-> Tuple[List[Action], float]:
        """
        Рассчитать список действий для балансировки и доступный свободный кэш
        :param portfolio: Открытые позиции
        :param index: Состав индекса
        :return: Список действий для балансировки и прогнозируемый остаток средств после балансировки
        """
        self.actions = []

        balancer = Balancer(portfolio, index)
        actions_list, free_cash = balancer.calculate_actions()

        for action in actions_list:
            share = self.broker.find_share(action.get("ticker"), "ticker")
            self.actions.append(Action(type=action.get("type"), quantity=action.get("quantity"), share=share))

        return self.actions, free_cash

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

if __name__ == "__main__":
    import pprint
    manager = PortfolioManager()

    account = manager.get_user_accounts()[0]

    portfolio = manager.get_portfolio(account)
    pprint.pprint(portfolio)
    index_moex = manager.get_index_list("IMOEX")

    actions, cash = manager.get_action_for_rebalance(portfolio, index_moex)
    print(f"{actions, cash}")

    success_action_list, error_action_list = manager.execute_actions()
    print(f"{success_action_list, error_action_list}")
