export type BaseInfo = {
  id: string;
  name: string;
};

export type BrokerInfoStrategy = {
  id: string;
  name: string;
  account: BaseInfo;
  /** Комиссия брокера долей ("0.003" = 0,3 %) — правится в настройках брокера. */
  commission: string;
};

/** Настройки расчёта по стратегии (PATCH /strategies/{id}). */
export type StrategySettings = {
  /** Неснижаемый остаток денег: балансировщик его не тратит на покупки. */
  maxCash: number;
  /** Допустимое отклонение от веса в индексе, долей ("0.05" = 5 %). */
  delta: string;
  /** Сколько лотов оставлять при продаже. */
  minLotsToKeep: number;
};

export type PortfolioStrategy = {
  uid: string;
  name: string;
  ticker: string;

  indexWeight: number;
  portfolioWeight: number;
  portfolioCount: number;

  offer: number | null;
};

export type UserStrategy = {
  id: string;

  brokerInfo: BrokerInfoStrategy;

  indexInfo: BaseInfo;

  portfolio: PortfolioStrategy[];

  freeCash: number;
  freeCashAfter: number;

  settings: StrategySettings;

  accountDeleted: boolean;
};

export type CurrentUserInfo = {
  id: string;
  /** null у пользователей, зарегистрированных только через Telegram. */
  email: string | null;
  telegramLinked: boolean;

  strategies: UserStrategy[];
};