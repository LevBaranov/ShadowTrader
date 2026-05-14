import { COLORS } from "../../../shared/theme/colors";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
} from "recharts";
import type { Asset } from "../types/rebalance";

type Props = {
  data: Asset[];
};


export default function PortfolioBar({ data }: Props) {
  return (
    <BarChart width={800} height={300} data={data}>
      <XAxis dataKey="ticker" />
      <YAxis />
      <Tooltip 
        contentStyle={{
          backgroundColor: "#2a2a2a",
          border: "none",
          color: "#fff",
        }}
      />
      <Legend 
        wrapperStyle={{
          color: "#ccc",
        }}
      />

      <Bar
          dataKey="indexWeight"
          name="В индексе"
          fill={COLORS.grayLight} 
      />

      <Bar
          dataKey="portfolioWeight"
          name="В портфеле"
          fill={COLORS.grayDark}
      />
    </BarChart>
  );
}