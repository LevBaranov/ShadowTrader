import { isAxiosError } from "axios";

/**
 * Машиночитаемый код ошибки из ответа бэкенда (detail).
 * У ошибок валидации FastAPI detail — массив, такие интересуют как «422», а не текст.
 */
export function errorDetail(error: unknown): string | null {
  if (!isAxiosError(error)) return null;

  const detail = error.response?.data?.detail;

  return typeof detail === "string" ? detail : null;
}

export function errorStatus(error: unknown): number | null {
  return isAxiosError(error) ? error.response?.status ?? null : null;
}

/** Код ошибки → текст для пользователя, иначе fallback. */
export function errorMessage(
  error: unknown,
  messages: Record<string, string>,
  fallback: string
): string {
  const detail = errorDetail(error);

  return (detail && messages[detail]) || fallback;
}
