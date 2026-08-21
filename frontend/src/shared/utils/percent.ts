/**
 * Доли и проценты.
 *
 * Бэкенд хранит и принимает доли: комиссия 0.003 — это 0,3 %, delta 0.05 — 5 %.
 * Пользователю доля непонятна, поэтому в интерфейсе всегда проценты, а перевод
 * живёт здесь — чтобы деление на 100 не размазывалось по компонентам.
 */

/** Сколько знаков после запятой оставляем в процентах: 0.00005 → 0,005 %. */
const PERCENT_PRECISION = 3;

/** Доля → проценты для показа: 0.003 → "0.3" (без хвоста 0.30000000000000004). */
export function fractionToPercent(fraction: number | string): string {
  const value = Number(fraction) * 100;

  // toFixed добавляет незначащие нули — убираем их через Number.
  return String(Number(value.toFixed(PERCENT_PRECISION)));
}

/**
 * Проценты из поля ввода → доля для API. null — введено некорректно.
 *
 * Пустую строку считаем нулём: «без комиссии» — осмысленный ввод.
 * Принимаем и запятую как разделитель — так набирают на русской раскладке.
 */
export function percentToFraction(value: string): number | null {
  const trimmed = value.trim().replace(/\s/g, "").replace(",", ".");
  if (trimmed === "") return 0;

  if (!/^\d*\.?\d*$/.test(trimmed) || trimmed === ".") return null;

  const percent = Number(trimmed);
  // Доля должна остаться в [0, 1): 100 % и выше — почти наверняка ошибка ввода.
  if (!Number.isFinite(percent) || percent < 0 || percent >= 100) return null;

  // Округляем, чтобы 0.3 / 100 не превратилось в 0.0030000000000000005.
  return Number((percent / 100).toFixed(PERCENT_PRECISION + 2));
}

/** Проценты словами для карточек и списков: 0.003 → "0.3 %". */
export const formatPercent = (fraction: number | string) =>
  `${fractionToPercent(fraction)} %`;
