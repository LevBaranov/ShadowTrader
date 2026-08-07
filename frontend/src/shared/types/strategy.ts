/** Лёгкий элемент списка стратегий (GET /strategies) — без портфеля. */
export type StrategyListItem = {
  id: string;
  brokerInfo: {
    id: string;
    name: string;
    account: { id: string; name: string };
  };
  indexInfo: { id: string; name: string };
  /** PK счёта в нашей БД. */
  brokersAccountId: string;
  accountDeleted: boolean;
};

export const strategyListLabel = (strategy: StrategyListItem) =>
  `${strategy.brokerInfo.name} / ` +
  `${strategy.brokerInfo.account.name || strategy.brokerInfo.account.id}` +
  ` → ${strategy.indexInfo.name}`;
