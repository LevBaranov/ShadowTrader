import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  MenuItem,
  Alert,
} from "@mui/material";
import { useState } from "react";

import { buttonStyles } from "../theme/buttons";
import { saveBroker } from "../api/brokers";
import { BROKER_NAMES, type BrokerSettings } from "../types/broker";
import { errorDetail } from "../utils/errors";
import { fractionToPercent, percentToFraction } from "../utils/percent";

/** Комиссия по умолчанию в процентах — как DEFAULT_COMMISSION (0.003) на бэкенде. */
const DEFAULT_COMMISSION_PERCENT = "0.3";

type Props = {
  open: boolean;
  onClose: () => void;
  onSaved: (broker: BrokerSettings) => void;
  /** Уже подключённый брокер: диалог работает как обновление токена доступа. */
  broker?: BrokerSettings | null;
};

export default function BrokerDialog({ open, onClose, onSaved, broker }: Props) {
  const [brokerName, setBrokerName] = useState(broker?.brokerName ?? BROKER_NAMES[0]);
  const [token, setToken] = useState("");
  // Пользователь вводит проценты, в API уходит доля.
  const [commission, setCommission] = useState(
    broker ? fractionToPercent(broker.commission) : DEFAULT_COMMISSION_PERCENT
  );

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const parsedCommission = percentToFraction(commission);

  const handleClose = () => {
    setToken("");
    setError("");

    onClose();
  };

  const handleSave = async () => {
    if (parsedCommission === null) return;

    try {
      setSaving(true);
      setError("");

      const saved = await saveBroker({
        brokerName,
        token,
        commission: parsedCommission,
      });

      handleClose();
      onSaved(saved);
    } catch (e) {
      console.error(e);

      setError(errorDetail(e) ?? "Не удалось сохранить брокера");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} fullWidth>
      <DialogTitle>
        {broker ? "Обновить токен брокера" : "Новый брокер"}
      </DialogTitle>

      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <TextField
          select
          fullWidth
          label="Брокер"
          value={brokerName}
          onChange={(e) => setBrokerName(e.target.value)}
          margin="normal"
          // При обновлении токена брокер уже определён.
          disabled={!!broker}
        >
          {BROKER_NAMES.map((name) => (
            <MenuItem key={name} value={name}>
              {name}
            </MenuItem>
          ))}
        </TextField>

        <TextField
          fullWidth
          label="Токен доступа"
          type="password"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          margin="normal"
          helperText="Токен хранится в зашифрованном виде и не показывается повторно"
        />

        <TextField
          fullWidth
          label="Комиссия по тарифу, %"
          value={commission}
          onChange={(e) => setCommission(e.target.value)}
          margin="normal"
          error={parsedCommission === null}
          helperText={
            parsedCommission === null
              ? "Введите комиссию в процентах, например 0.3"
              : "Учитывается при расчёте балансировки. Тариф Т-банка «Инвестор» — 0.3 %"
          }
        />
      </DialogContent>

      <DialogActions>
        <Button onClick={handleClose}>Отмена</Button>

        <Button
          sx={buttonStyles}
          onClick={handleSave}
          disabled={!token || parsedCommission === null || saving}
        >
          {saving ? "Сохранение..." : "Сохранить"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
