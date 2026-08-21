export type SortField =
  | "ticker"
  | "indexWeight"
  | "portfolioWeight"
  | "portfolioCount"
  | "offer";

export type SortDirection =
  | "asc"
  | "desc";

export type SortConfig = {
  field: SortField;
  direction: SortDirection;
};