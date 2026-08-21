import api from "../../../shared/api/client";
import type { NotificationChannel, UserProfile } from "../types/profile";

export const getProfile = async () => {
  const res = await api.get<UserProfile>("/users/me/profile");

  return res.data;
};

/** Куда отправлять уведомления планировщика. */
export const updateNotificationChannel = async (channel: NotificationChannel) => {
  const res = await api.patch<UserProfile>("/users/me/notifications", { channel });

  return res.data;
};

/**
 * Начать смену (или добавление) почты — код уходит на новый адрес.
 * password нужен, только если входа по почте ещё нет (регистрация через Telegram).
 */
export const requestEmailChange = async (email: string, password?: string) => {
  const res = await api.post<{ pendingEmail: string }>("/users/me/email", {
    email,
    ...(password ? { password } : {}),
  });

  return res.data;
};

export const confirmEmailChange = async (code: string) => {
  const res = await api.post<UserProfile>("/users/me/email/confirm", { code });

  return res.data;
};

export const resendEmailCode = async () => {
  const res = await api.post<{ pendingEmail: string }>("/users/me/email/resend");

  return res.data;
};

export const cancelEmailChange = async () => {
  await api.delete("/users/me/email/pending");
};
