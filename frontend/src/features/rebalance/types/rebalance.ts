export type Asset = {
  id: string;
  ticker: string;
  name: string;
  indexWeight: number;
  portfolioWeight: number;
  portfolioCount: number;
  // Может прийти null с бэкенда (PortfolioPosition.offer: int|None).
  offer: number | null;
};
export type Action = {
  type: "BUY" | "SELL";
  ticker: string;
  quantity: number;
};