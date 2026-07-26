export type BrokerSettings = {
  id: string;
  brokerName: string;
  sandbox: boolean;
};

export type BrokerAccount = {
  id: string;
  accountId: string;
  accountName: string;
  hasStrategy: boolean;
};

export type StockMarketIndex = {
  id: string;
  stockMarket: string;
  indexName: string;
  description?: string | null;
};

export type RebalanceExecutionResult = {
  success: string[];
  errors: string[];
};
