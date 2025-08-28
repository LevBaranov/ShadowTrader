import pandas as pd
from typing import List, Tuple, Dict

from src.config import settings

from src.models import Positions, Index


class Balancer:
    """
    Класс формирует балансировку. Сами действия он не выполняет, он только проводит расчёт

    """

    def __init__(self, positions: Positions, index: Index,
                 delta: float = settings.balancer.delta,
                 commission: float = settings.balancer.commission,
                 min_lots_to_keep: float = settings.balancer.min_lots_to_keep,
                 ):
        self.actions = []
        self.positions = positions
        self.index = index
        self.free_cash = positions.cash.to_float()

        self.delta = delta
        self.commission = commission
        self.min_lots_to_keep = min_lots_to_keep

    def __calculate_portfolio_value(self, portfolio_dataframe: pd.DataFrame) -> float:
        """Общая стоимость портфеля с учетом свободных средств"""
        if portfolio_dataframe.empty:
            return self.free_cash
        return (portfolio_dataframe['balance'] * portfolio_dataframe['last_price']).sum() + self.free_cash


    def create_weights_dataframe(self, index_dataframe: pd.DataFrame,
                                 portfolio_dataframe: pd.DataFrame,
                                 total: float)-> pd.DataFrame:
        """Создаём DataFrame с текущими и целевыми весами"""

        def calculate_weights(portfolio: pd.DataFrame, total: float):
            """Веса акций в текущем портфеле"""

            if portfolio.empty or total == 0:
                return pd.Series(dtype=float)

            return (portfolio['balance'] * portfolio['last_price']) / total

        current_weights = calculate_weights(portfolio_dataframe, total)
        df = index_dataframe[['weight', 'lot_size', 'last_price']].copy()
        df['target_weight'] = df['weight'] / 100
        df['current_weight'] = current_weights
        df['current_weight'] = pd.to_numeric(df['current_weight'], errors='coerce').fillna(0)
        df['ratio'] = df['current_weight'] / df['target_weight']
        df['over'] = (df['ratio'] > 1 + self.delta).astype(int)
        df = df.reset_index()

        # Добавляем акции, которых нет в индексе
        extra = portfolio_dataframe.index.difference(index_dataframe.index)
        if not extra.empty:
            rows = []
            for ticker in extra:
                rows.append({
                    'ticker': ticker,
                    'weight': 0,
                    'target_weight': 0,
                    'lot_size': portfolio_dataframe.at[ticker, 'lot_size'],
                    'last_price': portfolio_dataframe.at[ticker, 'last_price'],
                    'current_weight': current_weights.get(ticker, 0),
                    'ratio': 1,  # Высокий приоритет на продажу
                    'over': 1
                })
            df = pd.concat([df, pd.DataFrame(rows)], ignore_index=True)

        # Сортируем тикеры
        df.sort_values(by=['over', 'ratio', 'target_weight'],
                       ascending=[False, True, False], inplace=True)

        return df.set_index("ticker")


    def add_action(self, action_type: str, ticker_name: str, quantity: int):
        action_list = self.actions
        return action_list.append({
            'type': action_type,
            'ticker': ticker_name,
            'quantity': quantity
        })

    def optimize_actions(self) -> List[Dict]:
        """Объединяет однотипные действия для одного тикера"""

        optimized = []
        last_actions = {}

        for action in self.actions:
            ticker, action_type, qty = action['ticker'], action['type'], action['quantity']

            # Если в оптимизированном списке есть предыдущее действие для этого тикера
            if ticker in last_actions:
                last_index, last_action = last_actions[ticker]

                # Если между последним таким же действием был противоположный тип - сбрасываем
                if last_action != action_type:
                    optimized.append(action.copy())
                    last_actions[ticker] = (len(optimized) - 1, action_type)
                else:
                    # Объединяем количество
                    optimized[last_index]['quantity'] += qty
            else:
                # Добавляем новое действие, если его не было ранее
                optimized.append(action.copy())
                last_actions[ticker] = (len(optimized) - 1, action_type)

        return optimized

    def calculate_actions(self) -> Tuple[List[Dict], float]:

        portfolio_df = self.positions.shares_to_dataframe().set_index("ticker")
        index_df = self.index.to_dataframe().set_index("ticker")

        # Продаём что исключили из индекса
        total_value = self.__calculate_portfolio_value(portfolio_df)
        rebalanced = self.create_weights_dataframe(index_df, portfolio_df, total_value)
        exclude_positions = rebalanced[rebalanced['target_weight'] == 0]
        for ticker, position in exclude_positions.iterrows():
            self.add_action(
                "SELL",
                ticker,
                int(portfolio_df.at[ticker, 'balance'])
            )

        portfolio_df.drop(exclude_positions.index, inplace=True)

        while True:

            made_changes = False  # Флаг изменений
            total_value = self.__calculate_portfolio_value(portfolio_df)
            rebalanced = self.create_weights_dataframe(index_df, portfolio_df, total_value)

            # Векторизованные условия для покупки/продажи
            buy_condition = (rebalanced['target_weight'] >
                             rebalanced['current_weight'] * (1 + self.delta))
            sell_condition = ~buy_condition & (
                    rebalanced['current_weight'] > 0)
            # Обработка покупок
            buy_candidates = rebalanced[buy_condition]
            for ticker, row in buy_candidates.iterrows():
                lot_price = row['lot_size'] * row['last_price']
                total_cost = lot_price * (1 + self.commission)

                if total_cost < self.free_cash:
                    if ticker in portfolio_df.index:
                        portfolio_df.at[ticker, 'balance'] += row['lot_size']
                    else:
                        new_row = index_df.loc[ticker, ['lot_size', 'last_price']].copy()
                        new_row['balance'] = row['lot_size']
                        portfolio_df = pd.concat([portfolio_df, new_row.to_frame().T])

                    self.free_cash -= total_cost
                    self.add_action('BUY', ticker, 1)
                    made_changes = True
                    break

            # Обработка продаж
            if not made_changes:
                sell_candidates = rebalanced[sell_condition]
                for ticker, row in sell_candidates.iterrows():
                    balance = int(portfolio_df.at[ticker, 'balance'])
                    lot_size = row['lot_size']

                    if balance > lot_size:
                        shares_to_sell = 0
                        while (balance > lot_size and
                               (balance - lot_size) * row['last_price'] / total_value >= row[
                                   'target_weight'] and
                               balance // lot_size > self.min_lots_to_keep):
                            balance -= lot_size
                            shares_to_sell += 1

                        if shares_to_sell > 0:
                            sell_price = shares_to_sell * lot_size * row['last_price']
                            commission_fee = sell_price * self.commission

                            portfolio_df.at[ticker, 'balance'] = balance
                            self.free_cash += sell_price - commission_fee
                            self.add_action('SELL', ticker, shares_to_sell)
                            made_changes = True
                            break
            if not made_changes:
                break

        self.actions = self.optimize_actions()
        return self.actions, float(self.free_cash)



