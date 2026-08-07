import type { PortfolioStrategy, } from "../types/user";

import type { Asset, } from "../types/rebalance";

export function mapPortfolioToAssets( portfolio: PortfolioStrategy[] ): Asset[] {
  return portfolio.map(({ uid, offer, ...item }): Asset => ({
      ...item,
      id: uid,
      offer: offer ?? 0,
    }),
  );
}
