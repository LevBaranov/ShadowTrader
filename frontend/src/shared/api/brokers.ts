import api from "./client";
import type { BrokerSettings } from "../types/broker";

export const getBrokers = async () => {
  const res = await api.get<BrokerSettings[]>("/brokers");

  return res.data;
};

/**
 * Создать или обновить брокера: бэкенд ищет запись по имени брокера, так что
 * повторный вызов с тем же brokerName перезаписывает токен доступа.
 *
 * commission — доля (0.003 = 0,3 %); не передана — остаётся значение по умолчанию
 * у нового брокера или уже сохранённое у существующего.
 */
export const saveBroker = async (params: {
  brokerName: string;
  token: string;
  commission?: number;
}) => {
  const res = await api.put<BrokerSettings>("/brokers", params);

  return res.data;
};

/**
 * Настройки брокера без секретов — комиссия по тарифу. Отдельно от saveBroker:
 * менять комиссию не должно требовать повторного ввода токена.
 */
export const updateBroker = async (
  brokerId: string,
  params: { commission: number }
) => {
  const res = await api.patch<BrokerSettings>(`/brokers/${brokerId}`, params);

  return res.data;
};
