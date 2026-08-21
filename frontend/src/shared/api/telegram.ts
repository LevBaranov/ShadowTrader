import api from "./client";

/**
 * Подтвердить привязку Telegram кодом из бота.
 * Используется и страницей диплинка (/link-telegram), и разделом настроек.
 */
export const confirmTelegramLink = async (code: string) => {
  const res = await api.post<{ telegramId: number }>("/users/me/telegram-link", {
    code,
  });

  return res.data;
};

export const unlinkTelegram = async () => {
  await api.delete("/users/me/telegram-link");
};
