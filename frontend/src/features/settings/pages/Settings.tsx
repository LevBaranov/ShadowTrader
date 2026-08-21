import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Box,
  CircularProgress,
  Snackbar,
  Typography,
} from "@mui/material";

import { getAccounts, getStrategyList } from "../../../shared/api/accounts";
import { getBrokers } from "../../../shared/api/brokers";
import { getTasks } from "../../../shared/api/tasks";
import type { Account } from "../../../shared/types/account";
import type { BrokerSettings } from "../../../shared/types/broker";
import type { StrategyListItem } from "../../../shared/types/strategy";
import type { Task } from "../../../shared/types/task";
import { clearCurrentUserCache } from "../../rebalance/api/client";

import { getProfile } from "../api/client";
import type { UserProfile } from "../types/profile";
import BrokersSection from "../components/BrokersSection";
import EmailSection from "../components/EmailSection";
import NotificationsSection from "../components/NotificationsSection";
import TasksSection from "../components/TasksSection";
import TelegramSection from "../components/TelegramSection";

export default function Settings() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [brokers, setBrokers] = useState<BrokerSettings[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [strategies, setStrategies] = useState<StrategyListItem[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);

  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const reload = useCallback(async () => {
    const [profileData, brokerList, accountList, strategyList, taskList] =
      await Promise.all([
        getProfile(),
        getBrokers(),
        getAccounts(),
        getStrategyList(),
        getTasks(),
      ]);

    setProfile(profileData);
    setBrokers(brokerList);
    setAccounts(accountList);
    setStrategies(strategyList);
    setTasks(taskList);
    // Почта и брокеры видны и на главной — сбрасываем кэш /users/me.
    clearCurrentUserCache();
  }, []);

  useEffect(() => {
    const load = async () => {
      try {
        await reload();
      } catch (e) {
        console.error(e);

        setFailed(true);
        setError("Не удалось загрузить настройки");
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [reload]);

  const handleChanged = async () => {
    try {
      await reload();
    } catch (e) {
      console.error(e);

      setError("Не удалось обновить данные — перезагрузите страницу");
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", mt: 10 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!profile) {
    return (
      <Alert severity="error">
        Не удалось загрузить настройки. Обновите страницу.
      </Alert>
    );
  }

  const sectionProps = {
    onChanged: handleChanged,
    onError: setError,
    onInfo: setInfo,
  };

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 3, fontWeight: "bold" }}>
        Настройки
      </Typography>

      {failed && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          Часть данных могла не загрузиться.
        </Alert>
      )}

      <TasksSection
        tasks={tasks}
        strategies={strategies}
        accounts={accounts}
        {...sectionProps}
      />

      <BrokersSection
        brokers={brokers}
        accounts={accounts}
        onAccountsChanged={setAccounts}
        {...sectionProps}
      />

      <NotificationsSection profile={profile} {...sectionProps} />

      <EmailSection profile={profile} {...sectionProps} />

      <TelegramSection profile={profile} {...sectionProps} />

      <Snackbar
        open={!!error}
        autoHideDuration={5000}
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
