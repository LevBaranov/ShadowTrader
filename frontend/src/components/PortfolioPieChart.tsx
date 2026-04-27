import { PieChart, Pie, Cell, Tooltip } from "recharts";

import { COLORS } from "../theme/colors";

export default function PortfolioPieChart({ data }: any) {
  return (
    <PieChart width={300} height={300}>
      <Tooltip
        formatter={(value: number, name: string) => [`${value}%`, name]}
      />
      
      <Pie data={data} dataKey="portfolioWeight" nameKey="ticker" outerRadius={100}>
        {data.map((_, i) => (
          <Cell key={i} fill={COLORS.pie[i % COLORS.pie.length]}/>
        ))}
      </Pie>
    </PieChart>

  );
}