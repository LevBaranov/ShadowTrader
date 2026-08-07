/** Счёт пользователя у брокера в плоском списке (GET /accounts). */
export type Account = {
  /** PK счёта в нашей БД — им параметризуются стратегии и задачи. */
  id: string;
  /** Идентификатор счёта на стороне брокера. */
  accountId: string;
  accountName: string;
  hasStrategy: boolean;

  brokerId: string;
  brokerName: string;
  sandbox: boolean;
};

export const accountLabel = (account: Account) =>
  `${account.brokerName} / ${account.accountName || account.accountId}` +
  (account.sandbox ? " (песочница)" : "");
