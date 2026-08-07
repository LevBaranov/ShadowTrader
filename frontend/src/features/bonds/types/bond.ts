export type BondEventType = "OFFER" | "CALL_OPTION";

export type BondEvent = {
  type: BondEventType;
  /** ISO-дата события (YYYY-MM-DD). */
  date: string;
};

/** Облигация на счёте, по которой впереди есть событие (GET /bonds/events). */
export type BondWithEvents = {
  ticker: string;
  name?: string | null;
  figi?: string | null;
  /** Количество бумаг на счёте. */
  quantity: number;
  events: BondEvent[];
};

export const BOND_EVENT_LABELS: Record<BondEventType, string> = {
  OFFER: "Оферта",
  CALL_OPTION: "Колл-опцион",
};

/**
 * ISO-дата события в локальную Date.
 * Через new Date("YYYY-MM-DD") строка читается как UTC-полночь и в части
 * часовых поясов съезжает на день назад, поэтому разбираем по частям.
 */
export const parseEventDate = (value: string): Date => {
  const [year, month, day] = value.split("-").map(Number);

  return new Date(year, (month ?? 1) - 1, day ?? 1);
};
