import type { Action, Asset, } from "../types/rebalance";

export function buildRebalanceActions( assets: Asset[] ): Action[] {

  const actions: Action[] = [];
  for (const row of assets) {
    // offer может быть null/NaN/дробным — в лоты идёт только целое > 0.
    if (typeof row.offer !== "number" || !Number.isFinite(row.offer) || row.offer === 0) {
      continue;
    }
    const quantity = Math.round(Math.abs(row.offer));
    if (quantity <= 0) {
      continue;
    }
    actions.push({
      type: row.offer > 0 ? "BUY" : "SELL",
      ticker: row.ticker,
      quantity,
    });
  }
  return actions;
} 