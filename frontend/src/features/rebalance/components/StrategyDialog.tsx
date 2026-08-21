import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  MenuItem,
  Alert,
  CircularProgress,
  Box,
  IconButton,
} from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import { useEffect, useState } from "react";
import { buttonStyles } from "../../../shared/theme/buttons";
import { parseAmount } from "../../../shared/utils/amount";
import { errorDetail } from "../../../shared/utils/errors";
import { percentToFraction } from "../../../shared/utils/percent";

import {
  getBrokerAccounts,
  refreshBrokerAccounts,
  getIndices,
  createStrategy,
} from "../api/client";
import { getBrokers } from "../../../shared/api/brokers";
import type { BrokerAccount, StockMarketIndex } from "../types/strategy";
import type { BrokerSettings } from "../../../shared/types/broker";
import BrokerDialog from "../../../shared/components/BrokerDialog";

type Props = {
  open: boolean;
  onClose: () => void;
  onSave: () => void;
};

export default function StrategyDialog({ open, onClose, onSave }: Props) {
  const [brokers, setBrokers] = useState<BrokerSettings[]>([]);
  const [accounts, setAccounts] = useState<BrokerAccount[]>([]);
  const [indices, setIndices] = useState<StockMarketIndex[]>([]);

  const [brokerId, setBrokerId] = useState("");
  const [accountId, setAccountId] = useState("");
  const [indexId, setIndexId] = useState("");
  const [maxCash, setMaxCash] = useState("0");
  // Значения по умолчанию совпадают с дефолтами в БД: 5 % и 1 лот.
  const [delta, setDelta] = useState("5");
  const [minLots, setMinLots] = useState("1");

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [brokerDialog, setBrokerDialog] = useState(false);

  useEffect(() => {
    if (!open) return;

    const load = async () => {
      try {
        setLoading(true);
        setError("");

        const [brokerList, indexList] = await Promise.all([
          getBrokers(),
          getIndices(),
        ]);

        setBrokers(brokerList);
        setIndices(indexList);

        // Без брокера стратегию не создать — сразу открываем форму добавления.
        if (brokerList.length === 0) {
          setBrokerDialog(true);
        }
      } catch (e) {
        console.error(e);

        setError("Не удалось загрузить справочники");
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [open]);

  useEffect(() => {
    if (!brokerId) {
      setAccounts([]);
      setAccountId("");

      return;
    }

    const load = async () => {
      try {
        setError("");

        setAccounts(await getBrokerAccounts(brokerId));
      } catch (e) {
        console.error(e);

        setError(errorDetail(e) ?? "Не удалось загрузить счета брокера");
      }
    };

    load();
  }, [brokerId]);

  const handleClose = () => {
    setBrokerId("");
    setAccountId("");
    setIndexId("");
    setMaxCash("0");
    setDelta("5");
    setMinLots("1");
    setError("");

    onClose();
  };

  const handleRefreshAccounts = async () => {
    try {
      setRefreshing(true);
      setError("");

      const fresh = await refreshBrokerAccounts(brokerId);

      setAccounts(fresh);
      // Выбранный счёт мог пропасть у брокера — сбрасываем выбор.
      if (!fresh.some((account) => account.id === accountId)) {
        setAccountId("");
      }
    } catch (e) {
      console.error(e);

      setError(errorDetail(e) ?? "Не удалось обновить счета брокера");
    } finally {
      setRefreshing(false);
    }
  };

  const handleBrokerSaved = (broker: BrokerSettings) => {
    setBrokerDialog(false);

    setBrokers((prev) => [
      ...prev.filter((b) => b.id !== broker.id),
      broker,
    ]);
    // Сразу выбираем нового брокера — это же подтянет его счета.
    setBrokerId(broker.id);
  };

  const parsedMaxCash = parseAmount(maxCash);
  const parsedDelta = percentToFraction(delta);
  const parsedMinLots = parseAmount(minLots);

  const settingsInvalid =
    parsedMaxCash === null || parsedDelta === null || parsedMinLots === null;

  const handleSave = async () => {
    try {
      setSaving(true);
      setError("");

      await createStrategy({
        brokersAccountId: accountId,
        stockMarketsIndexId: indexId,
        maxCash: parsedMaxCash ?? 0,
        delta: parsedDelta ?? undefined,
        minLotsToKeep: parsedMinLots ?? undefined,
      });

      handleClose();
      onSave();
    } catch (e) {
      console.error(e);

      setError(errorDetail(e) ?? "Не удалось создать стратегию");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} fullWidth>
      <DialogTitle>Новая стратегия</DialogTitle>

      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {loading ? (
          <Box sx={{ textAlign: "center", py: 3 }}>
            <CircularProgress />
          </Box>
        ) : (
          <>
            {brokers.length === 0 && !error && (
              <Alert
                severity="info"
                sx={{ mb: 2 }}
                action={
                  <Button
                    size="small"
                    onClick={() => setBrokerDialog(true)}
                  >
                    Добавить
                  </Button>
                }
              >
                У вас пока нет брокеров — добавьте брокера с токеном доступа
              </Alert>
            )}

            <TextField
              select
              fullWidth
              label="Брокер"
              value={brokerId}
              onChange={(e) => setBrokerId(e.target.value)}
              margin="normal"
            >
              {brokers.map((broker) => (
                <MenuItem key={broker.id} value={broker.id}>
                  {broker.brokerName}
                  {broker.sandbox ? " (песочница)" : ""}
                </MenuItem>
              ))}
            </TextField>

            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 1,
              }}
            >
              <TextField
                select
                fullWidth
                label="Счёт"
                value={accountId}
                onChange={(e) => setAccountId(e.target.value)}
                margin="normal"
                disabled={!brokerId || refreshing}
              >
                {accounts.map((account) => (
                  <MenuItem
                    key={account.id}
                    value={account.id}
                    disabled={account.hasStrategy}
                  >
                    {account.accountName || "Без названия"}
                    {account.hasStrategy ? " — занят" : ""}
                  </MenuItem>
                ))}
              </TextField>

              <IconButton
                onClick={handleRefreshAccounts}
                disabled={!brokerId || refreshing}
                title="Обновить список счетов"
              >
                {refreshing ? (
                  <CircularProgress size={24} />
                ) : (
                  <RefreshIcon />
                )}
              </IconButton>
            </Box>

            <TextField
              select
              fullWidth
              label="Индекс"
              value={indexId}
              onChange={(e) => setIndexId(e.target.value)}
              margin="normal"
            >
              {indices.map((index) => (
                <MenuItem key={index.id} value={index.id}>
                  {index.indexName}
                  {index.description ? ` — ${index.description}` : ""}
                  {` (${index.stockMarket})`}
                </MenuItem>
              ))}
            </TextField>

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
          </>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={handleClose}>Отмена</Button>

        <Button
          sx={buttonStyles}
          onClick={handleSave}
          disabled={!accountId || !indexId || settingsInvalid || saving}
        >
          {saving ? "Сохранение..." : "Сохранить"}
        </Button>
      </DialogActions>

      <BrokerDialog
        open={brokerDialog}
        onClose={() => setBrokerDialog(false)}
        onSaved={handleBrokerSaved}
      />
    </Dialog>
  );
}
