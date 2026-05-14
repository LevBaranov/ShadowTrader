import { PieChart, Pie, Tooltip } from "recharts";

import { COLORS } from "../../../shared/theme/colors";
import type { Asset } from "../types/rebalance";

type Props = {
  data: Asset[];
};

export default function PortfolioPieChart({ data }: Props) {
  const coloredData = data.map((item: Asset, i: number) => ({
    ...item,
    fill: COLORS.pie[i % COLORS.pie.length],
  }));
  return (
    <PieChart width={300} height={300}>
      <Tooltip
        formatter={(value, name) => [`${value}%`, name]}
      />
      <Pie
        data={coloredData}
        dataKey="portfolioWeight"
        nameKey="ticker"
        outerRadius={100}
      />
    </PieChart>

  );
}