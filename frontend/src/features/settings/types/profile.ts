/** Куда пользователь получает уведомления планировщика. */
export type NotificationChannel = "TELEGRAM" | "EMAIL" | "ALL";

/** Профиль пользователя (GET /users/me/profile). */
export type UserProfile = {
  /** Подтверждённая почта. null у пользователей, зарегистрированных через Telegram. */
  email: string | null;
  /** Почта, ожидающая подтверждения кодом (начатая смена/добавление). */
  pendingEmail: string | null;
  telegramLinked: boolean;
  notificationChannel: NotificationChannel;
};

export const NOTIFICATION_CHANNEL_LABELS: Record<NotificationChannel, string> = {
  TELEGRAM: "Telegram",
  EMAIL: "Почта",
  ALL: "Telegram и почта",
};
