import { useEffect, useState } from "react";
import { Typography } from "@mui/material";
import { getBonds } from "../services/api";

import { DataGrid } from '@mui/x-data-grid';

export default function Bonds() {
  const [data, setData] = useState<any[]>([]);
  const columns = [
    { field: "name", headerName: "Облигация", width: 200 },
    { field: "date", headerName: "Дата", width: 150 },
    { field: "type", headerName: "Тип", width: 150 },
  ];
  useEffect(() => {
    getBonds().then(setData); // TODO API
  }, []);

  return (
    <>

      <div style={{ height: 400 , width: '100%' }}>
        <DataGrid rows={data} columns={columns} />
      </div>
    </>
  );
}