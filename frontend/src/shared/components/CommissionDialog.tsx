import { useState } from "react";
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
  Typography,
} from "@mui/material";

import { buttonStyles } from "../theme/buttons";
import { updateBroker } from "../api/brokers";
import type { BrokerSettings } from "../types/broker";
import { errorDetail } from "../utils/errors";
import { fractionToPercent, percentToFraction } from "../utils/percent";

type Props = {
  open: boolean;
  broker: BrokerSettings;
  onClose: () => void;
  onSaved: () => Promise<void> | void;
};

/**
 * Комиссия брокера по тарифу. Отдельный диалог, а не поле в BrokerDialog:
 * менять комиссию не должно требовать повторного ввода токена доступа.
 */
export default function CommissionDialog({ open, broker, onClose, onSaved }: Props) {
  const [value, setValue] = useState(fractionToPercent(broker.commission));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const parsed = percentToFraction(value);

  const handleClose = () => {
    setError("");
    onClose();
  };

  const handleSave = async () => {
    if (parsed === null) return;

    if (parsed === Number(broker.commission)) {
      handleClose();
      return;
    }

    try {
      setSaving(true);
      setError("");

      await updateBroker(broker.id, { commission: parsed });

      handleClose();
      await onSaved();
    } catch (e) {
      console.error(e);

      setError(errorDetail(e) ?? "Не удалось сохранить комиссию");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} fullWidth>
      <DialogTitle>Комиссия {broker.brokerName}</DialogTitle>

      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Typography color="text.secondary" sx={{ mb: 2 }}>
          Комиссия по вашему тарифу — она учитывается при расчёте балансировки для
          всех счетов и стратегий этого брокера.
        </Typography>

        <TextField
          fullWidth
          label="Комиссия, %"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          error={parsed === null}
          helperText={
            parsed === null
              ? "Введите комиссию в процентах, например 0.3"
              : "Тариф Т-банка «Инвестор» — 0.3 %"
          }
        />
      </DialogContent>

      <DialogActions>
        <Button onClick={handleClose} disabled={saving}>
          Отмена
        </Button>

        <Button
          sx={buttonStyles}
          onClick={handleSave}
          disabled={saving || parsed === null}
        >
          {saving ? "Сохранение..." : "Сохранить"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
