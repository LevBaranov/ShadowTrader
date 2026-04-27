import { mockPortfolio } from "../mocks/portfolio";
import { mockRebalance } from "../mocks/rebalance";
import { mockBonds } from "../mocks/bonds";

// TODO: заменить на реальные API вызовы

export const getPortfolio = async () => {
  return Promise.resolve(mockPortfolio);
};

export const getRebalance = async () => {
  return Promise.resolve(mockRebalance);
};

export const getBonds = async () => {
  return Promise.resolve(mockBonds);
};

export const executeRebalance = async (actions: any[]) => {
  console.log("EXECUTE:", actions);

  // имитация запроса
  await new Promise((res) => setTimeout(res, 2000));

  return {
    success: actions.map(
      (a) =>
        `${a.type === "BUY" ? "Куплено" : "Продано"} ${a.ticker} (${a.quantity} шт)`
    ),
    errors: [],
  };
};
