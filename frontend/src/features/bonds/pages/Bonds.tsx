import { useEffect, useState } from "react";
import { Typography } from "@mui/material";
import { DataGrid, type GridColDef } from '@mui/x-data-grid';
import { getBonds } from "../api/client";

const columns: GridColDef[] = [
    { field: "name", headerName: "Облигация", width: 200 },
    { field: "date", headerName: "Дата", width: 150 },
    { field: "type", headerName: "Тип", width: 150 },
  ];

export default function Bonds() {
  const [data, setData] = useState<any[]>([]);
  
  useEffect(() => {
    getBonds().then(setData); // TODO API
  }, []);

  return (
    <>
      <Typography
        variant="h5"
        sx={{
          mb: 3,
          fontWeight: "bold",
        }}
      >
        Раздел в разработке. На текущий момент показывает погоду на Марсе
      </Typography>
      <div style={{ height: 400 , width: '100%' }}>
        <DataGrid rows={data} columns={columns} />
      </div>
    </>
  );
}