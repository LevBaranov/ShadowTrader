import { useState } from "react";
import {
  Alert,
  Button,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemText,
  Typography,
} from "@mui/material";

import { deleteTask } from "../../../shared/api/tasks";
import type { Account } from "../../../shared/types/account";
import type { StrategyListItem } from "../../../shared/types/strategy";
import { taskLabel, thresholdLabel, type Task } from "../../../shared/types/task";

type Props = {
  tasks: Task[];
  strategies: StrategyListItem[];
  accounts: Account[];
  onChanged: () => Promise<void> | void;
  onError: (message: string) => void;
  onInfo: (message: string) => void;
};

const formatLastRun = (value?: string | null) => {
  if (!value) return "ещё не запускалась";

  const parsed = new Date(value);

  return Number.isNaN(parsed.getTime())
    ? value
    : `последний запуск ${parsed.toLocaleDateString("ru-RU")}`;
};

export default function TasksSection({
  tasks,
  strategies,
  accounts,
  onChanged,
  onError,
  onInfo,
}: Props) {
  const [busyId, setBusyId] = useState("");

  const handleCancel = async (task: Task) => {
    try {
      setBusyId(task.id);

      await deleteTask(task.id);

      await onChanged();
      onInfo("Задача отменена");
    } catch (e) {
      console.error(e);

      onError("Не удалось отменить задачу");
    } finally {
      setBusyId("");
    }
  };

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Задачи по расписанию
        </Typography>

        {tasks.length === 0 ? (
          <Alert severity="info">
            Задач нет. Автобалансировку включают на карточке стратегии,
            мониторинг облигаций — в разделе «Облигации».
          </Alert>
        ) : (
          <List disablePadding>
            {tasks.map((task) => (
              <ListItem
                key={task.id}
                divider
                secondaryAction={
                  <Button
                    size="small"
                    onClick={() => handleCancel(task)}
                    disabled={busyId === task.id}
                  >
                    Отменить
                  </Button>
                }
              >
                <ListItemText
                  primary={taskLabel(task, strategies, accounts)}
                  secondary={[thresholdLabel(task), formatLastRun(task.lastCheckedDate)]
                    .filter(Boolean)
                    .join(", ")}
                />
              </ListItem>
            ))}
          </List>
        )}
      </CardContent>
    </Card>
  );
}
