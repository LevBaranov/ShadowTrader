import { DataGrid } from "@mui/x-data-grid";

export default function PortfolioTable({ data }: any) {
 const columns = [
    { field: 'id', headerName: 'ID', width: 10 },
    { field: 'ticker', headerName: 'Тикер', width: 100 },
    { field: 'name', headerName: 'Название', width: 150 },
    { field: 'indexWeight', headerName: 'Вес в индексе', width: 120 },
    { field: 'portfolioWeight', headerName: 'Вес в портфеле', width: 140 },
    { field: 'quantity', headerName: 'Колво в портфеле', width: 150 },
    {
      field: 'diff',
      headerName: 'Разница',
      width: 100,
      renderCell: (params: any) => {
        const value = params.value;

        let color = 'inherit';
        if (value < 0) color = 'red';
        if (value > 0) color = 'green';

        return <span style={{ color }}>{value}</span>;
      },
    },
  ];
  return (
    <div style={{ height: 400 , width: '100%' }}>
      <DataGrid rows={data} columns={columns} />
    </div>
  );
}