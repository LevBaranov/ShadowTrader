import api from "../../../shared/api/client";
import type { BondWithEvents } from "../types/bond";

/**
 * Облигации на счёте, по которым впереди оферта или колл-опцион.
 * Счёт — любой свой, со стратегиями не связан.
 */
export const getBondEvents = async (brokersAccountId: string) => {
  const res = await api.get<BondWithEvents[]>("/bonds/events", {
    params: { brokersAccountId },
  });

  return res.data;
};
