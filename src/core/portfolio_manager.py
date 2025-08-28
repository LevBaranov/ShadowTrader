import datetime
from typing import List, Tuple, Dict, Optional

from src.core.balancer import Balancer

from src.models import Action, Positions, Account, Index, Error

from src.services.broker import TBroker, TAccount
from src.services.stock_market import Moex


class PortfolioManager:
    """
    Класс для управления портфелем. Смотрит текущие позиции, анализирует индекс,
    рассчитывает что нужно сделать для балансировки
    """

    def __init__(self, account_id: str = None):
        self.actions: List[Action] = []
        self.broker = TBroker()
        if account_id:
            self.set_account(account_id)
        else:
            self.account_client: Optional[TAccount] = None
        self._index_cache: Dict[Tuple[str, datetime.date], Index] = {}
        self._indices_cache: Dict[datetime.date, List[Tuple[str, str]]] = {}
        self.moex = Moex()

    def get_user_accounts(self) -> List[Account]:
        """
        Получить список всех доступных пользователю аккаунтов
        :return: Список аккаунтов
        """
        return self.broker.get_all_accounts()

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

    def get_indices_list(self) -> List[Tuple[str, str]]:
        """
        Получить список индексов, кешируя результат на день
        :return: Список: Индекс, краткое название
        """
        today = datetime.date.today()
        if today not in self._indices_cache:
            idx = self.moex.get_indices()
            self._indices_cache[today] = idx
        return self._indices_cache[today]

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

    portfolio = manager.get_portfolio(account.id)
    pprint.pprint(portfolio)
    index_moex = manager.get_index_list("IMOEX")

    actions, cash = manager.get_action_for_rebalance(portfolio, index_moex)
    pprint.pprint(actions)
    pprint.pprint(cash)

    # success_action_list, error_action_list = manager.execute_actions()
    # print(f"{success_action_list, error_action_list}")
