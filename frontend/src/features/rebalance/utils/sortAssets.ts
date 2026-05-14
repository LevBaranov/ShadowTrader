import type {
  Asset,
} from "../types/rebalance";

import type {
  SortConfig,
} from "../types/sort";

export function sortAssets(
  assets: Asset[],
  config: SortConfig
): Asset[] {
  const sorted = [...assets];

  sorted.sort((a, b) => {
    const aValue = a[config.field];
    const bValue = b[config.field];

    if (typeof aValue === "string") {
      return config.direction === "asc"
        ? aValue.localeCompare(
            String(bValue)
          )
        : String(bValue).localeCompare(
            aValue
          );
    }

    return config.direction === "asc"
      ? Number(aValue) -
          Number(bValue)
      : Number(bValue) -
          Number(aValue);
  });

  return sorted;
}