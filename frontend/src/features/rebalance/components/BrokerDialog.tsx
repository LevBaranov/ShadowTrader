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
import { isAxiosError } from "axios";
import { buttonStyles } from "../../../shared/theme/buttons";

import { saveBroker } from "../api/client";
import type { BrokerSettings } from "../types/strategy";

// Должен соответствовать BrokerNames на бэкенде (src/models/broker_names.py).
const BROKER_NAMES = ["T-Bank"];

type Props = {
  open: boolean;
  onClose: () => void;
  onSaved: (broker: BrokerSettings) => void;
};

export default function BrokerDialog({ open, onClose, onSaved }: Props) {
  const [brokerName, setBrokerName] = useState(BROKER_NAMES[0]);
  const [token, setToken] = useState("");

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleClose = () => {
    setToken("");
    setError("");

    onClose();
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError("");

      const broker = await saveBroker({
        brokerName,
        token,
      });

      handleClose();
      onSaved(broker);
    } catch (e) {
      console.error(e);

      const detail =
        isAxiosError(e) && typeof e.response?.data?.detail === "string"
          ? e.response.data.detail
          : null;

      setError(detail ?? "Не удалось сохранить брокера");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} fullWidth>
      <DialogTitle>Новый брокер</DialogTitle>

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

        {/*<FormControlLabel*/}
        {/*  control={*/}
        {/*    <Checkbox*/}
        {/*      checked={sandbox}*/}
        {/*      onChange={(e) => setSandbox(e.target.checked)}*/}
        {/*    />*/}
        {/*  }*/}
        {/*  label="Песочница"*/}
        {/*/>*/}
      </DialogContent>

      <DialogActions>
        <Button onClick={handleClose}>Отмена</Button>

        <Button
          sx={buttonStyles}
          onClick={handleSave}
          disabled={!token || saving}
        >
          {saving ? "Сохранение..." : "Сохранить"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
