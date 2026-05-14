export type BaseInfo = {
  id: string;
  name: string;
};

export type BrokerInfoStrategy = {
  id: string;
  name: string;
  account: BaseInfo;
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
  brokerInfo: BrokerInfoStrategy;

  indexInfo: BaseInfo;

  portfolio: PortfolioStrategy[];

  freeCash: number;
};

export type CurrentUserInfo = {
  id: string;
  email: string;

  strategies: UserStrategy[];
};