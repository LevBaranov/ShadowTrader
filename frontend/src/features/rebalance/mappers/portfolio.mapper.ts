import type { PortfolioStrategy, } from "../types/user";

import type { Asset, } from "../types/rebalance";

export function mapPortfolioToAssets( portfolio: PortfolioStrategy[] ): Asset[] {
  // return portfolio.map((item) => ({
  //   id: item.uid,
  //   ticker: item.ticker,
  //   name: item.name,
  //   indexWeight: item.indexWeight,
  //   portfolioWeight: item.portfolioWeight,
  //   portfolioCount: item.portfolioCount,
  //   offer: item.offer ?? 0,

  return portfolio.map(({ uid, offer, ...item }): Asset => ({
      ...item,
      id: uid,
      offer: offer ?? 0,
    }),
  );
}
