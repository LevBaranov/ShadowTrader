import api from "../../../shared/api/client";
import type { CurrentUserInfo } from "../types/user";
import type {
  BrokerAccount,
  StockMarketIndex,
  RebalanceExecutionResult,
} from "../types/strategy";

let mePromise: Promise<CurrentUserInfo> | null = null;


export const getCurrentUser = async (force = false) => {
  if (!mePromise || force) {
    mePromise = api
      .get<CurrentUserInfo>("/users/me")
      .then((res) => res.data)
      .catch((error) => {
        // Не кэшируем ошибку: иначе после истечения токена и повторного
        // логина сюда навсегда «залипает» отклонённый промис и запрос
        // /users/me больше не выполняется.
        mePromise = null;

        throw error;
      });
  }
  return mePromise;
};

export const clearCurrentUserCache = () => {
  mePromise = null;
};


type RebalanceApiResult = {
  success?: { type: string; ticker?: string | null; quantity: number }[];
  errors?: {
    type?: string | null;
    ticker?: string | null;
    quantity?: number | null;
    description?: string | null;
  }[];
};

export const executeRebalance = async (
  strategyId: string
): Promise<RebalanceExecutionResult> => {
  const res = await api.post<RebalanceApiResult>("/portfolios/balance", {
    strategyId,
  });

  const { success = [], errors = [] } = res.data ?? {};

  return {
    success: success.map(
      (a) =>
        `${a.type === "SELL" ? "Продано" : "Куплено"} ${a.ticker ?? "?"} (${a.quantity} шт)`
    ),
    errors: errors.map((e) => {
      const action = e.type === "SELL" ? "продать" : "купить";
      const target = e.ticker
        ? ` ${e.ticker}${e.quantity ? ` (${e.quantity} шт)` : ""}`
        : "";

      return `Не удалось ${action}${target}: ${e.description ?? "неизвестная ошибка"}`;
    }),
  };
};


export const getBrokerAccounts = async (brokerId: string) => {
  const res = await api.get<BrokerAccount[]>(
    `/brokers/${brokerId}/accounts`
  );

  return res.data;
};

export const refreshBrokerAccounts = async (brokerId: string) => {
  const res = await api.post<BrokerAccount[]>(
    `/brokers/${brokerId}/accounts/refresh`
  );

  return res.data;
};

export const getIndices = async () => {
  const res = await api.get<StockMarketIndex[]>("/indices");

  return res.data;
};

export const createStrategy = async (params: {
  brokersAccountId: string;
  stockMarketsIndexId: string;
  /** Неснижаемый остаток денег: балансировщик его не тратит на покупки. */
  maxCash?: number;
  /** Допустимое отклонение от веса в индексе, долей (0.05 = 5 %). */
  delta?: number;
  minLotsToKeep?: number;
}) => {
  const res = await api.post("/strategies", params);

  return res.data;
};

/**
 * Настройки расчёта по стратегии. Счёт и индекс не меняются — это новая
 * стратегия. Комиссия здесь не участвует: это тариф брокера (updateBroker).
 */
export const updateStrategy = async (
  strategyId: string,
  params: { maxCash: number; delta: number; minLotsToKeep: number }
) => {
  const res = await api.patch(`/strategies/${strategyId}`, params);

  return res.data;
};

export const deleteStrategy = async (strategyId: string) => {
  await api.delete(`/strategies/${strategyId}`);
};
