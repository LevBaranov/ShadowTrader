import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  CircularProgress,
} from "@mui/material";
import { useState } from "react";
import { buttonStyles } from "../../../shared/theme/buttons";
import type { Action } from "../types/rebalance";
import type { RebalanceExecutionResult } from "../types/strategy";


type Props = {
  open: boolean;
  onClose: () => void;
  actions: Action[];
  onExecute: () => Promise<RebalanceExecutionResult>;
};

export default function RebalanceDialog({
  open,
  onClose,
  actions,
  onExecute
}: Props) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RebalanceExecutionResult | null>(null);

  const handleClose = () => {
    setLoading(false);
    setResult(null);
    onClose();
  };

  const handleExecute = async () => {
    try {
      setLoading(true);

      setResult(await onExecute());
    } catch (e) {
      console.error(e);

      setResult({
        success: [],
        errors: ["Не удалось выполнить балансировку"],
      });
    } finally {
      setLoading(false);
    }
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
                <li
                  key={i}
                  style={{ color: a.type === "SELL" ? "red" : "green" }}
                >
                  {a.type === "SELL" ? "Продать" : "Купить"} {a.ticker} в количестве {a.quantity} шт.
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
            {result.success.length === 0 ? (
              <div>Нет</div>
            ) : (
              <ul>
                {result.success.map((a: string, i: number) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            )}

            <b>Ошибки:</b>
            {result.errors.length === 0 ? (
              <div>Нет</div>
            ) : (
              <ul>
                {result.errors.map((e: string, i: number) => (
                  <li key={i} style={{ color: "red" }}>{e}</li>
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
