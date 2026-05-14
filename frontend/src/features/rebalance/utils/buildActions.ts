import type { Action, Asset, } from "../types/rebalance";

export function buildRebalanceActions( assets: Asset[] ): Action[] {
  
  return assets.filter((row: Asset) => row.offer !== 0)
    .map((row: Asset) => ({
      type: row.offer > 0 ? "BUY" : "SELL",
      ticker: row.ticker,
      quantity: Math.abs(row.offer),
    }));
} 