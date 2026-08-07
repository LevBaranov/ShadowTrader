import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  IconButton,
  MenuItem,
  Snackbar,
  TextField,
  Typography,
} from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import NotificationsActiveIcon from "@mui/icons-material/NotificationsActive";
import NotificationsOffIcon from "@mui/icons-material/NotificationsOff";

import { buttonStyles } from "../../../shared/theme/buttons";
import { getAccounts, refreshAccounts } from "../../../shared/api/accounts";
import { createTask, deleteTask, findTask, getTasks } from "../../../shared/api/tasks";
import { accountLabel, type Account } from "../../../shared/types/account";
import type { Task } from "../../../shared/types/task";
import { errorMessage } from "../../../shared/utils/errors";

import { getBondEvents } from "../api/client";
import type { BondWithEvents } from "../types/bond";
import BondEventsTable from "../components/BondEventsTable";

const CHECK_ERRORS: Record<string, string> = {
  account_not_found: "Счёт не найден — обновите список счетов",
};

export default function Bonds() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [accountId, setAccountId] = useState("");

  const [bonds, setBonds] = useState<BondWithEvents[] | null>(null);
  const [checkedAccountId, setCheckedAccountId] = useState("");

  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [savingTask, setSavingTask] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const loadTasks = async () => setTasks(await getTasks());

  useEffect(() => {
    const load = async () => {
      try {
        const [accountList] = await Promise.all([getAccounts(), loadTasks()]);

        setAccounts(accountList);
        // Один счёт — выбирать не из чего, сразу подставляем.
        if (accountList.length === 1) {
          setAccountId(accountList[0].id);
        }
      } catch (e) {
        console.error(e);

        setError("Не удалось загрузить счета");
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  // Задача мониторинга привязана к счёту, а не к результату проверки.
  const monitorTask = checkedAccountId
    ? findTask(tasks, "BOND_EVENTS_MONITOR", {
        brokers_account_id: checkedAccountId,
      })
    : null;

  const handleRefreshAccounts = async () => {
    try {
      setRefreshing(true);
      setError("");

      const fresh = await refreshAccounts();

      setAccounts(fresh);
      // Выбранный счёт мог закрыться у брокера — сбрасываем выбор и результат.
      if (!fresh.some((account) => account.id === accountId)) {
        setAccountId("");
        setBonds(null);
        setCheckedAccountId("");
      }
      setInfo("Список счетов обновлён");
    } catch (e) {
      console.error(e);

      setError("Не удалось обновить счета");
    } finally {
      setRefreshing(false);
    }
  };

  const handleCheck = async () => {
    try {
      setChecking(true);
      setError("");
      setBonds(null);

      const result = await getBondEvents(accountId);

      setBonds(result);
      setCheckedAccountId(accountId);
    } catch (e) {
      console.error(e);

      setError(errorMessage(e, CHECK_ERRORS, "Не удалось проверить облигации"));
    } finally {
      setChecking(false);
    }
  };

  const handleEnableMonitor = async () => {
    try {
      setSavingTask(true);
      setError("");

      await createTask({
        type: "BOND_EVENTS_MONITOR",
        frequency: "WEEKLY",
        params: { brokers_account_id: checkedAccountId },
      });

      await loadTasks();
      setInfo("Буду сообщать о событиях по этому счёту");
    } catch (e) {
      console.error(e);

      // Задача уже могла появиться (например, включена в боте) — подтянем состояние.
      await loadTasks();
      setError(
        errorMessage(
          e,
          { task_already_exists: "Уведомления по этому счёту уже включены" },
          "Не удалось включить уведомления"
        )
      );
    } finally {
      setSavingTask(false);
    }
  };

  const handleDisableMonitor = async () => {
    if (!monitorTask) return;

    try {
      setSavingTask(true);
      setError("");

      await deleteTask(monitorTask.id);

      await loadTasks();
      setInfo("Уведомления отключены");
    } catch (e) {
      console.error(e);

      setError("Не удалось отключить уведомления");
    } finally {
      setSavingTask(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", mt: 10 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 3, fontWeight: "bold" }}>
        Облигации
      </Typography>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography color="text.secondary" sx={{ mb: 2 }}>
            Выберите счёт брокера, на котором проверить облигации. Это не связано
            со стратегиями — доступен любой счёт.
          </Typography>

          {accounts.length === 0 ? (
            <Alert severity="info">
              Нет счетов у брокеров. Подключите брокера в разделе «Настройки».
            </Alert>
          ) : (
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 1,
                flexWrap: "wrap",
              }}
            >
              <TextField
                select
                label="Счёт"
                value={accountId}
                onChange={(e) => setAccountId(e.target.value)}
                sx={{ minWidth: 320 }}
                disabled={refreshing}
              >
                {accounts.map((account) => (
                  <MenuItem key={account.id} value={account.id}>
                    {accountLabel(account)}
                  </MenuItem>
                ))}
              </TextField>

              <IconButton
                onClick={handleRefreshAccounts}
                disabled={refreshing}
                title="Обновить список счетов"
              >
                {refreshing ? <CircularProgress size={24} /> : <RefreshIcon />}
              </IconButton>

              <Button
                sx={buttonStyles}
                onClick={handleCheck}
                disabled={!accountId || checking}
              >
                {checking ? "Проверяю..." : "Проверить"}
              </Button>
            </Box>
          )}
        </CardContent>
      </Card>

      {checking && (
        <Box sx={{ display: "flex", justifyContent: "center", my: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {bonds !== null && !checking && (
        <Card>
          <CardContent>
            <Box
              sx={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                mb: 2,
                gap: 2,
                flexWrap: "wrap",
              }}
            >
              <Typography variant="h6">
                Предстоящие оферты и колл-опционы
              </Typography>

              {monitorTask ? (
                <Button
                  startIcon={<NotificationsOffIcon />}
                  onClick={handleDisableMonitor}
                  disabled={savingTask}
                >
                  Не сообщать о событиях
                </Button>
              ) : (
                <Button
                  sx={buttonStyles}
                  startIcon={<NotificationsActiveIcon />}
                  onClick={handleEnableMonitor}
                  disabled={savingTask}
                >
                  Сообщить о событии
                </Button>
              )}
            </Box>

            {monitorTask && (
              <Alert severity="success" sx={{ mb: 2 }}>
                Проверяю этот счёт раз в неделю и напишу, когда событие будет
                близко.
              </Alert>
            )}

            {bonds.length === 0 ? (
              <Alert severity="info">
                На этом счёте нет облигаций с предстоящей офертой или
                колл-опционом.
              </Alert>
            ) : (
              <BondEventsTable bonds={bonds} />
            )}
          </CardContent>
        </Card>
      )}

      <Snackbar
        open={!!error}
        autoHideDuration={4000}
        onClose={() => setError("")}
      >
        <Alert severity="error">{error}</Alert>
      </Snackbar>

      <Snackbar open={!!info} autoHideDuration={3000} onClose={() => setInfo("")}>
        <Alert severity="success">{info}</Alert>
      </Snackbar>
    </Box>
  );
}
