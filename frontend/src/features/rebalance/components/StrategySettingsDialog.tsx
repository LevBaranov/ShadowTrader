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

import { buttonStyles } from "../../../shared/theme/buttons";
import { parseAmount } from "../../../shared/utils/amount";
import { errorDetail } from "../../../shared/utils/errors";
import { fractionToPercent, percentToFraction } from "../../../shared/utils/percent";

import { updateStrategy } from "../api/client";
import type { StrategySettings } from "../types/user";

type Props = {
  open: boolean;
  onClose: () => void;
  strategyId: string;
  settings: StrategySettings;
  onSaved: () => Promise<void> | void;
};

/**
 * Настройки расчёта по стратегии. Комиссии здесь нет: это тариф брокера, он
 * общий для всех его счетов и правится в разделе «Брокеры и счета».
 */
export default function StrategySettingsDialog({
  open,
  onClose,
  strategyId,
  settings,
  onSaved,
}: Props) {
  const [maxCash, setMaxCash] = useState(String(settings.maxCash));
  // delta приходит долей, пользователю показываем проценты.
  const [delta, setDelta] = useState(fractionToPercent(settings.delta));
  const [minLots, setMinLots] = useState(String(settings.minLotsToKeep));

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const parsedMaxCash = parseAmount(maxCash);
  const parsedDelta = percentToFraction(delta);
  const parsedMinLots = parseAmount(minLots);

  const invalid =
    parsedMaxCash === null || parsedDelta === null || parsedMinLots === null;

  const unchanged =
    parsedMaxCash === settings.maxCash &&
    parsedDelta === Number(settings.delta) &&
    parsedMinLots === settings.minLotsToKeep;

  const handleClose = () => {
    setError("");
    onClose();
  };

  const handleSave = async () => {
    if (invalid) return;

    if (unchanged) {
      handleClose();
      return;
    }

    try {
      setSaving(true);
      setError("");

      await updateStrategy(strategyId, {
        maxCash: parsedMaxCash,
        delta: parsedDelta,
        minLotsToKeep: parsedMinLots,
      });

      handleClose();
      await onSaved();
    } catch (e) {
      console.error(e);

      setError(errorDetail(e) ?? "Не удалось сохранить настройки стратегии");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} fullWidth>
      <DialogTitle>Настройки стратегии</DialogTitle>

      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Typography color="text.secondary" sx={{ mb: 2 }}>
          Как балансировать этот портфель. Комиссия брокера — общая для всех его
          счетов и настраивается в разделе «Брокеры и счета».
        </Typography>

        <TextField
          fullWidth
          label="Неснижаемый остаток, ₽"
          value={maxCash}
          onChange={(e) => setMaxCash(e.target.value)}
          margin="normal"
          error={parsedMaxCash === null}
          helperText={
            parsedMaxCash === null
              ? "Введите целую сумму в рублях"
              : "Эти деньги балансировка не тратит на покупки. 0 — тратить весь свободный кэш"
          }
        />

        <TextField
          fullWidth
          label="Допустимое отклонение от индекса, %"
          value={delta}
          onChange={(e) => setDelta(e.target.value)}
          margin="normal"
          error={parsedDelta === null}
          helperText={
            parsedDelta === null
              ? "Введите отклонение в процентах, например 5"
              : "Пока вес бумаги отличается от индекса меньше чем на эту величину, её не трогаем"
          }
        />

        <TextField
          fullWidth
          label="Минимум лотов к сохранению"
          value={minLots}
          onChange={(e) => setMinLots(e.target.value)}
          margin="normal"
          error={parsedMinLots === null}
          helperText={
            parsedMinLots === null
              ? "Введите целое число лотов"
              : "Сколько лотов оставить в портфеле, даже если вес бумаги превышен"
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
          disabled={saving || invalid}
        >
          {saving ? "Сохранение..." : "Сохранить"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
