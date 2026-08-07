import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  List,
  ListItem,
  ListItemText,
  Typography,
} from "@mui/material";

import { buttonStyles } from "../../../shared/theme/buttons";
import BrokerDialog from "../../../shared/components/BrokerDialog";
import CommissionDialog from "../../../shared/components/CommissionDialog";
import { refreshAccounts } from "../../../shared/api/accounts";
import { accountLabel, type Account } from "../../../shared/types/account";
import type { BrokerSettings } from "../../../shared/types/broker";
import { errorDetail } from "../../../shared/utils/errors";
import { formatPercent } from "../../../shared/utils/percent";

type Props = {
  brokers: BrokerSettings[];
  accounts: Account[];
  onChanged: () => Promise<void> | void;
  onAccountsChanged: (accounts: Account[]) => void;
  onError: (message: string) => void;
  onInfo: (message: string) => void;
};

export default function BrokersSection({
  brokers,
  accounts,
  onChanged,
  onAccountsChanged,
  onError,
  onInfo,
}: Props) {
  const [dialogBroker, setDialogBroker] = useState<BrokerSettings | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [commissionBroker, setCommissionBroker] = useState<BrokerSettings | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const openDialog = (broker: BrokerSettings | null) => {
    setDialogBroker(broker);
    setDialogOpen(true);
  };

  const handleSaved = async () => {
    setDialogOpen(false);
    await onChanged();
    onInfo(dialogBroker ? "Токен брокера обновлён" : "Брокер подключён");
  };

  const handleCommissionSaved = async () => {
    setCommissionBroker(null);
    await onChanged();
    onInfo("Комиссия обновлена");
  };

  const handleRefresh = async () => {
    try {
      setRefreshing(true);

      onAccountsChanged(await refreshAccounts());
      onInfo("Список счетов обновлён");
    } catch (e) {
      console.error(e);

      // 422 от бэкенда приходит с готовым текстом («Токен брокера недействителен»).
      onError(errorDetail(e) ?? "Не удалось обновить счета");
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 2,
            flexWrap: "wrap",
            mb: 2,
          }}
        >
          <Typography variant="h6">Брокеры и счета</Typography>

          <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
            <Button
              onClick={handleRefresh}
              disabled={refreshing || brokers.length === 0}
              startIcon={refreshing ? <CircularProgress size={16} /> : undefined}
            >
              Обновить счета
            </Button>

            <Button sx={buttonStyles} onClick={() => openDialog(null)}>
              Подключить брокера
            </Button>
          </Box>
        </Box>

        {brokers.length === 0 ? (
          <Alert severity="info">
            Брокер не подключён. Добавьте API-токен, чтобы появились счета,
            стратегии и проверка облигаций.
          </Alert>
        ) : (
          <List disablePadding>
            {brokers.map((broker) => (
              <ListItem
                key={broker.id}
                divider
                secondaryAction={
                  <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                    <Button
                      size="small"
                      onClick={() => setCommissionBroker(broker)}
                    >
                      Комиссия
                    </Button>

                    <Button size="small" onClick={() => openDialog(broker)}>
                      Обновить токен
                    </Button>
                  </Box>
                }
              >
                <ListItemText
                  primary={
                    broker.brokerName + (broker.sandbox ? " (песочница)" : "")
                  }
                  secondary={
                    `Комиссия: ${formatPercent(broker.commission)} · ` +
                    `счетов: ${
                      accounts.filter((a) => a.brokerId === broker.id).length
                    }`
                  }
                />
              </ListItem>
            ))}
          </List>
        )}

        {accounts.length > 0 && (
          <>
            <Divider sx={{ my: 2 }} />

            <Typography color="text.secondary" sx={{ mb: 1 }}>
              Счета
            </Typography>

            <List disablePadding>
              {accounts.map((account) => (
                <ListItem key={account.id} disableGutters>
                  <ListItemText
                    primary={accountLabel(account)}
                    secondary={account.accountId}
                  />

                  {account.hasStrategy && (
                    <Chip size="small" label="есть стратегия" />
                  )}
                </ListItem>
              ))}
            </List>
          </>
        )}
      </CardContent>

      <BrokerDialog
        // Пересоздаём диалог под цель: подключение нового или обновление токена.
        key={dialogBroker?.id ?? "new"}
        open={dialogOpen}
        broker={dialogBroker}
        onClose={() => setDialogOpen(false)}
        onSaved={handleSaved}
      />

      {commissionBroker && (
        <CommissionDialog
          // Стартовое значение поля — текущая комиссия.
          key={`${commissionBroker.id}-${commissionBroker.commission}`}
          open
          broker={commissionBroker}
          onClose={() => setCommissionBroker(null)}
          onSaved={handleCommissionSaved}
        />
      )}
    </Card>
  );
}
