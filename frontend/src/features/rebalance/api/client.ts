import api from "../../../shared/api/client";
import type { CurrentUserInfo } from "../types/user";

let mePromise: Promise<any> | null = null;


export const getCurrentUser = async () => {
  // const res = ;
  if (!mePromise) {
    mePromise = api.get<CurrentUserInfo>("/users/me").then(res => res.data);
  }
  return mePromise;
};


export const executeRebalance = async (actions: any[]) => {

  await api.post("/portfolios/balance");

  return {
    success: actions.map(
      (a) =>
        `${a.type === "BUY" ? "Куплено" : "Продано"} ${a.ticker} (${a.quantity} шт)`
    ),
    errors: [],
  };
};