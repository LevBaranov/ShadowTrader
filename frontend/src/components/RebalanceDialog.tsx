import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  CircularProgress,
} from "@mui/material";
import { useState } from "react";
import { executeRebalance } from "../services/api";
import { buttonStyles } from "../theme/buttons";

type Action = {
  type: "BUY" | "SELL";
  ticker: string;
  quantity: number;
};

type Props = {
  open: boolean;
  onClose: () => void;
  actions: Action[];
};

export default function RebalanceDialog({ open, onClose, actions }: Props) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any | null>(null);

  const handleClose = () => {
    setLoading(false);
    setResult(null);
    onClose();
  };

  const handleExecute = async () => {
    setLoading(true);

    const res = await executeRebalance(actions);

    setLoading(false);
    setResult(res);
  };

  return (
    <Dialog open={open} onClose={handleClose} fullWidth>
      <DialogTitle>Подтверждение</DialogTitle>

      <DialogContent>
        {!loading && !result && (
          <>
            <div>Вы действительно хотите выполнить действия:</div>

            <ul>
              {actions.map((a, i) => (
                <li key={i}>
                  {a.type === "BUY" ? "Купить" : "Продать"} {a.ticker} в количестве {a.quantity} шт.
                </li>
              ))}
            </ul>
          </>
        )}

        {loading && (
          <div style={{ textAlign: "center", padding: 20 }}>
            <CircularProgress />
            <div>Выполнение...</div>
          </div>
        )}

        {result && (
          <div>
            <b>Успешно:</b>
            <ul>
              {result.success.map((a: string, i: number) => (
                <li key={i}>{a}</li>
              ))}
            </ul>

            <b>Ошибки:</b>
            {result.errors.length === 0 ? (
              <div>Нет</div>
            ) : (
              <ul>
                {result.errors.map((e: string, i: number) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </DialogContent>

      <DialogActions>
        {!loading && !result && (
          <>
            <Button onClick={handleClose}>Нет</Button>

            <Button sx={buttonStyles} onClick={handleExecute}>
              Да
            </Button>
          </>
        )}

        {result && (
          <Button onClick={handleClose}>
            Закрыть
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}