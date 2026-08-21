import api from "./client";
import type { Frequency, Task, TaskParams, TaskType } from "../types/task";

export const getTasks = async () => {
  const res = await api.get<Task[]>("/tasks");

  return res.data;
};

export const createTask = async (params: {
  type: TaskType;
  frequency: Frequency;
  params: TaskParams;
}) => {
  const res = await api.post<Task>("/tasks", params);

  return res.data;
};

/**
 * Поменять расписание и настройки существующей задачи, не пересоздавая её
 * (последний запуск сохраняется). Ссылку на стратегию/счёт менять нельзя.
 */
export const updateTask = async (
  taskId: string,
  changes: { frequency?: Frequency; params?: Pick<TaskParams, "min_free_cash"> }
) => {
  const res = await api.patch<Task>(`/tasks/${taskId}`, changes);

  return res.data;
};

export const deleteTask = async (taskId: string) => {
  await api.delete(`/tasks/${taskId}`);
};

/** Активная задача нужного типа по объекту из params. */
export const findTask = (
  tasks: Task[],
  type: TaskType,
  params: Pick<TaskParams, "strategy_id" | "brokers_account_id">
) =>
  tasks.find(
    (task) =>
      task.type === type &&
      Object.entries(params).every(
        ([key, value]) => task.params?.[key as keyof TaskParams] === value
      )
  ) ?? null;
