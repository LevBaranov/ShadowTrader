import type { Account } from "./account";
import { accountLabel } from "./account";
import type { StrategyListItem } from "./strategy";
import { strategyListLabel } from "./strategy";

export type TaskType = "REBALANCE" | "BOND_EVENTS_MONITOR";

export type Frequency = "WEEKLY" | "MONTHLY" | "QUARTERLY";

/**
 * Настройки задачи. Ключи snake_case — так они лежат в params в БД.
 *
 * strategy_id / brokers_account_id — на какой объект настроена задача,
 * после создания не меняются. min_free_cash — настройка планировщика для
 * REBALANCE: порог свободного кэша, ниже которого балансировка не запускается.
 */
export type TaskParams = {
  strategy_id?: string;
  brokers_account_id?: string;
  min_free_cash?: number;
};

/** Задача планировщика (GET /tasks). */
export type Task = {
  id: string;
  type: TaskType;
  frequency: Frequency;
  params?: TaskParams | null;
  lastCheckedDate?: string | null;
};

export const FREQUENCY_LABELS: Record<Frequency, string> = {
  WEEKLY: "раз в неделю",
  MONTHLY: "раз в месяц",
  QUARTERLY: "раз в квартал",
};

export const TASK_TYPE_LABELS: Record<TaskType, string> = {
  REBALANCE: "Автобалансировка",
  BOND_EVENTS_MONITOR: "События по облигациям",
};

/** Человекочитаемое описание задачи: что, как часто и по какому объекту. */
export function taskLabel(
  task: Task,
  strategies: StrategyListItem[],
  accounts: Account[]
): string {
  const kind = TASK_TYPE_LABELS[task.type] ?? task.type;
  const frequency = FREQUENCY_LABELS[task.frequency] ?? task.frequency;

  const strategyId = task.params?.strategy_id;
  const accountId = task.params?.brokers_account_id;

  let target = "";
  if (strategyId) {
    const strategy = strategies.find((s) => s.id === strategyId);
    if (strategy) target = ` — ${strategyListLabel(strategy)}`;
  } else if (accountId) {
    const account = accounts.find((a) => a.id === accountId);
    if (account) target = ` — ${accountLabel(account)}`;
  }

  return `${kind}, ${frequency}${target}`;
}

/** Порог автобалансировки словами — для описания задачи в настройках. */
export function thresholdLabel(task: Task): string | null {
  if (task.type !== "REBALANCE") return null;

  const threshold = task.params?.min_free_cash;
  if (!threshold) return "запускается при любом свободном кэше";

  return `запускается от ${threshold.toLocaleString("ru-RU")} ₽ свободного кэша`;
}
