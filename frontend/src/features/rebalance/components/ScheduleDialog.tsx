import { useState } from "react";
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  TextField,
  Typography,
} from "@mui/material";

import { buttonStyles } from "../../../shared/theme/buttons";
import { createTask, deleteTask, updateTask } from "../../../shared/api/tasks";
import {
  FREQUENCY_LABELS,
  type Frequency,
  type Task,
} from "../../../shared/types/task";
import { parseAmount } from "../../../shared/utils/amount";
import { errorMessage } from "../../../shared/utils/errors";

const FREQUENCIES: Frequency[] = ["WEEKLY", "MONTHLY", "QUARTERLY"];

/** Порог по умолчанию для новой задачи — как на бэкенде (DEFAULT_MIN_FREE_CASH). */
const DEFAULT_MIN_FREE_CASH = 2000;

type Props = {
  open: boolean;
  onClose: () => void;
  strategyId: string;
  /** Уже включённая автобалансировка по этой стратегии. */
  task: Task | null;
  onSaved: () => Promise<void> | void;
};

/**
 * Автобалансировка стратегии — задача REBALANCE для планировщика.
 * Настройки задачи: частота и порог свободного кэша, ниже которого не запускаемся.
 */
export default function ScheduleDialog({
  open,
  onClose,
  strategyId,
  task,
  onSaved,
}: Props) {
  const [frequency, setFrequency] = useState<Frequency>(
    task?.frequency ?? "WEEKLY"
  );
  const [minFreeCash, setMinFreeCash] = useState(
    String(task?.params?.min_free_cash ?? DEFAULT_MIN_FREE_CASH)
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const parsedMinFreeCash = parseAmount(minFreeCash);

  const handleClose = () => {
    setError("");
    onClose();
  };

  const handleSave = async () => {
    if (parsedMinFreeCash === null) return;

    // Ничего не меняется — не дёргаем бэкенд зря.
    if (
      task &&
      task.frequency === frequency &&
      (task.params?.min_free_cash ?? 0) === parsedMinFreeCash
    ) {
      handleClose();
      return;
    }

    try {
      setSaving(true);
      setError("");

      if (task) {
        // Правим существующую задачу на месте: последний запуск сохраняется.
        await updateTask(task.id, {
          frequency,
          params: { min_free_cash: parsedMinFreeCash },
        });
      } else {
        await createTask({
          type: "REBALANCE",
          frequency,
          params: {
            strategy_id: strategyId,
            min_free_cash: parsedMinFreeCash,
          },
        });
      }

      handleClose();
      await onSaved();
    } catch (e) {
      console.error(e);

      setError(
        errorMessage(
          e,
          { task_already_exists: "Автобалансировка по этой стратегии уже включена" },
          task
            ? "Не удалось изменить автобалансировку"
            : "Не удалось включить автобалансировку"
        )
      );
    } finally {
      setSaving(false);
    }
  };

  const handleDisable = async () => {
    if (!task) return;

    try {
      setSaving(true);
      setError("");

      await deleteTask(task.id);

      handleClose();
      await onSaved();
    } catch (e) {
      console.error(e);

      setError("Не удалось отключить автобалансировку");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} fullWidth>
      <DialogTitle>Автобалансировка</DialogTitle>

      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Typography color="text.secondary" sx={{ mb: 2 }}>
          Планировщик сам приведёт портфель к индексу, когда на счёте накопится
          свободный кэш.
        </Typography>

        <TextField
          select
          fullWidth
          label="Как часто балансировать"
          value={frequency}
          onChange={(e) => setFrequency(e.target.value as Frequency)}
        >
          {FREQUENCIES.map((value) => (
            <MenuItem key={value} value={value}>
              {FREQUENCY_LABELS[value]}
            </MenuItem>
          ))}
        </TextField>

        <TextField
          fullWidth
          label="Запускать от суммы, ₽"
          value={minFreeCash}
          onChange={(e) => setMinFreeCash(e.target.value)}
          margin="normal"
          error={parsedMinFreeCash === null}
          helperText={
            parsedMinFreeCash === null
              ? "Введите целую сумму в рублях"
              : "Меньше этой суммы свободного кэша — планировщик пропустит запуск. 0 — балансировать при любой сумме"
          }
        />
      </DialogContent>

      <DialogActions>
        {task && (
          <Button onClick={handleDisable} disabled={saving}>
            Отключить
          </Button>
        )}

        <Button onClick={handleClose} disabled={saving}>
          Отмена
        </Button>

        <Button
          sx={buttonStyles}
          onClick={handleSave}
          disabled={saving || parsedMinFreeCash === null}
        >
          {saving ? "Сохранение..." : task ? "Изменить" : "Включить"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
