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
import { isAxiosError } from "axios";
import { buttonStyles } from "../../../shared/theme/buttons";

import {
  getBrokers,
  getBrokerAccounts,
  refreshBrokerAccounts,
  getIndices,
  createStrategy,
} from "../api/client";
import type {
  BrokerSettings,
  BrokerAccount,
  StockMarketIndex,
} from "../types/strategy";
import BrokerDialog from "./BrokerDialog";

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

        const detail =
          isAxiosError(e) && typeof e.response?.data?.detail === "string"
            ? e.response.data.detail
            : null;

        setError(detail ?? "Не удалось загрузить счета брокера");
      }
    };

    load();
  }, [brokerId]);

  const handleClose = () => {
    setBrokerId("");
    setAccountId("");
    setIndexId("");
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

      const detail =
        isAxiosError(e) && typeof e.response?.data?.detail === "string"
          ? e.response.data.detail
          : null;

      setError(detail ?? "Не удалось обновить счета брокера");
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

  const handleSave = async () => {
    try {
      setSaving(true);
      setError("");

      await createStrategy({
        brokersAccountId: accountId,
        stockMarketsIndexId: indexId,
      });

      handleClose();
      onSave();
    } catch (e) {
      console.error(e);

      const detail =
        isAxiosError(e) && typeof e.response?.data?.detail === "string"
          ? e.response.data.detail
          : null;

      setError(detail ?? "Не удалось создать стратегию");
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
          </>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={handleClose}>Отмена</Button>

        <Button
          sx={buttonStyles}
          onClick={handleSave}
          disabled={!accountId || !indexId || saving}
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
