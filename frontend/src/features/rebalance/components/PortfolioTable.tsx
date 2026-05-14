import { DataGrid } from "@mui/x-data-grid";
import type { GridColDef, GridRenderCellParams } from "@mui/x-data-grid";
import type { Asset } from "../types/rebalance";

type Props = {
  data: Asset[];
};
const columns: GridColDef[] = [
    { field: 'ticker', headerName: 'Тикер', width: 100 },
    { field: 'name', headerName: 'Название', width: 250 },
    { field: 'indexWeight', headerName: 'Вес в индексе', width: 120 },
    { field: 'portfolioWeight', headerName: 'Вес в портфеле', width: 150 },
    { field: 'portfolioCount', headerName: 'Колво в портфеле', width: 150 },
    {
      field: 'offer',
      headerName: 'Предложение по покупке',
      width: 200,
      renderCell: (params: GridRenderCellParams) => {
        const value = params.value;

        let color = 'inherit';
        if (value < 0) color = 'red';
        if (value > 0) color = 'green';

        return (<span style={{ color }}>{value}</span>);
      },
    },
  ];
export default function PortfolioTable({ data }: Props) {

  return (
    <div style={{ height: 1000 , width: '100%' }}>
      <DataGrid rows={data} columns={columns} />
    </div>
  );
}