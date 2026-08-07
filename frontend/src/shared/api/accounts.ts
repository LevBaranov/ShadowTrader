import api from "./client";
import type { Account } from "../types/account";
import type { StrategyListItem } from "../types/strategy";

/** Все счета пользователя по всем брокерам. */
export const getAccounts = async () => {
  const res = await api.get<Account[]>("/accounts");

  return res.data;
};

/** Пересинхронизировать счета со всеми брокерами. */
export const refreshAccounts = async () => {
  const res = await api.post<Account[]>("/accounts/refresh");

  return res.data;
};

/** Лёгкий список стратегий — нужен, чтобы называть задачи и счета. */
export const getStrategyList = async () => {
  const res = await api.get<StrategyListItem[]>("/strategies");

  return res.data;
};
