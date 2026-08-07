/**
 * Денежная настройка из текстового поля: неотрицательное целое число рублей.
 * null — значение введено некорректно, сохранять нельзя.
 *
 * Пустую строку трактуем как 0: «не оставлять ничего» — осмысленный выбор.
 */
export function parseAmount(value: string): number | null {
  const trimmed = value.trim().replace(/\s/g, "");
  if (trimmed === "") return 0;

  if (!/^\d+$/.test(trimmed)) return null;

  const parsed = Number(trimmed);

  return Number.isSafeInteger(parsed) ? parsed : null;
}

export const formatAmount = (value: number) => value.toLocaleString("ru-RU");
