export type BrokerSettings = {
  id: string;
  brokerName: string;
  sandbox: boolean;
  /**
   * Комиссия брокера долей: "0.003" — это 0,3 %. Приходит строкой (Decimal
   * на бэкенде). В интерфейсе показываем проценты — см. shared/utils/percent.ts.
   */
  commission: string;
};

// Должен соответствовать BrokerNames на бэкенде (src/models/broker_names.py).
export const BROKER_NAMES = ["T-Bank"];
