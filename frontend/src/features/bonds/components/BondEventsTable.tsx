import { useMemo } from "react";
import { DataGrid, type GridColDef } from "@mui/x-data-grid";

import {
  BOND_EVENT_LABELS,
  parseEventDate,
  type BondWithEvents,
} from "../types/bond";

const columns: GridColDef[] = [
  { field: "ticker", headerName: "Тикер", width: 160 },
  { field: "name", headerName: "Облигация", flex: 1, minWidth: 180 },
  { field: "quantity", headerName: "Кол-во", width: 100 },
  { field: "event", headerName: "Событие", width: 160 },
  { field: "date", headerName: "Дата события", type: "date", width: 160 },
];

/** Одна строка на событие: у бумаги их может быть несколько (оферта и колл-опцион). */
function toRows(bonds: BondWithEvents[]) {
  return bonds.flatMap((bond) =>
    bond.events.map((event, index) => ({
      id: `${bond.ticker}-${event.type}-${index}`,
      ticker: bond.ticker,
      name: bond.name ?? "—",
      quantity: bond.quantity,
      event: BOND_EVENT_LABELS[event.type] ?? event.type,
      date: parseEventDate(event.date),
    }))
  );
}

export default function BondEventsTable({ bonds }: { bonds: BondWithEvents[] }) {
  const rows = useMemo(() => toRows(bonds), [bonds]);

  return (
    <div style={{ width: "100%" }}>
      <DataGrid
        rows={rows}
        columns={columns}
        autoHeight
        disableRowSelectionOnClick
        initialState={{
          // Ближайшие события — сверху.
          sorting: { sortModel: [{ field: "date", sort: "asc" }] },
        }}
        pageSizeOptions={[10, 25, 50]}
      />
    </div>
  );
}
