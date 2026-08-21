export type Asset = {
  id: string;
  ticker: string;
  name: string;
  indexWeight: number;
  portfolioWeight: number;
  portfolioCount: number;
  offer: number;
};
export type Action = {
  type: "BUY" | "SELL";
  ticker: string;
  quantity: number;
};