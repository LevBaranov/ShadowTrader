import { useCallback, useEffect, useState } from "react";
import {
  Box,
  Typography,
  Button,
  CircularProgress,
} from "@mui/material";


import { buttonStyles } from "../../../shared/theme/buttons";
import { findTask, getTasks } from "../../../shared/api/tasks";
import type { Task } from "../../../shared/types/task";

import StrategyDialog from "../components/StrategyDialog";
import type {
  UserStrategy
} from "../types/user";
import { useCurrentUser } from "../hooks/useCurrentUser";
import StrategyCard from "../components/StrategyCard";


export default function Rebalance() {
  const { user, loading, refresh, } = useCurrentUser();
  const [strategyDialog, setStrategyDialog] = useState(false);
  // Задачи планировщика: по ним видно, включена ли автобалансировка стратегии.
  const [tasks, setTasks] = useState<Task[]>([]);

  const loadTasks = useCallback(async () => {
    try {
      setTasks(await getTasks());
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    const load = async () => {
      await loadTasks();
    };

    load();
  }, [loadTasks]);

  const dialog = (
    <StrategyDialog
      open={strategyDialog}
      onClose={() =>
        setStrategyDialog(false)
      }
      onSave={async () => {
        await refresh();
      }}
    />
  );

  if (loading) {
    return (
      <Box
        sx={{
          display: "flex",
          justifyContent: "center",
          mt: 10,
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if ( !user || !user.strategies || user.strategies.length === 0 ) {
    return (
      <Box
        sx={{
          textAlign: "center",
          mt: 10,
        }}
      >
        <Typography
          variant="h5"
          sx={{ mb: 2 }}
        >
          У вас пока нет стратегий
        </Typography>

        <Button
          variant="contained"
          sx={buttonStyles}
          onClick={() =>
            setStrategyDialog(true)
          }
        >
          Добавить стратегию
        </Button>

        {dialog}
      </Box>
    );
  }

  return (
    <Box>
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          mb: 3,
        }}
      >
        <Typography
          variant="h5"
          sx={{ fontWeight: "bold" }}
        >
          Портфели
        </Typography>

        <Button
          variant="contained"
          sx={buttonStyles}
          onClick={() =>
            setStrategyDialog(true)
          }
        >
          Добавить стратегию
        </Button>
      </Box>

      {user.strategies.map(
        (
          strategy: UserStrategy
        ) => (
          <StrategyCard
            key={strategy.id}
            strategy={strategy}
            scheduleTask={findTask(tasks, "REBALANCE", {
              strategy_id: strategy.id,
            })}
            onUpdated={refresh}
            onScheduleChanged={loadTasks}
          />
        )
      )}

      {dialog}
    </Box>
  );
}
