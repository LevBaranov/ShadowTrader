import { useState } from "react";
import {
  Alert,
  Card,
  CardContent,
  FormControl,
  FormControlLabel,
  Radio,
  RadioGroup,
  Typography,
} from "@mui/material";

import { errorMessage } from "../../../shared/utils/errors";

import { updateNotificationChannel } from "../api/client";
import {
  NOTIFICATION_CHANNEL_LABELS,
  type NotificationChannel,
  type UserProfile,
} from "../types/profile";

const ERRORS: Record<string, string> = {
  telegram_not_linked: "Сначала привяжите Telegram — ниже в этом разделе",
  email_not_confirmed: "Сначала добавьте и подтвердите почту",
  no_channels_available: "Нет ни одного канала: привяжите Telegram или добавьте почту",
};

type Props = {
  profile: UserProfile;
  onChanged: () => Promise<void> | void;
  onError: (message: string) => void;
  onInfo: (message: string) => void;
};

const CHANNELS: NotificationChannel[] = ["TELEGRAM", "EMAIL", "ALL"];

/** Куда планировщик присылает результаты автобалансировки и события по облигациям. */
export default function NotificationsSection({
  profile,
  onChanged,
  onError,
  onInfo,
}: Props) {
  const [busy, setBusy] = useState(false);

  const unavailable = (channel: NotificationChannel) => {
    if (channel === "TELEGRAM") return !profile.telegramLinked;
    if (channel === "EMAIL") return !profile.email;

    return !profile.telegramLinked && !profile.email;
  };

  const handleChange = async (channel: NotificationChannel) => {
    if (channel === profile.notificationChannel) return;

    try {
      setBusy(true);

      await updateNotificationChannel(channel);

      await onChanged();
      onInfo(`Уведомления: ${NOTIFICATION_CHANNEL_LABELS[channel]}`);
    } catch (e) {
      console.error(e);

      onError(errorMessage(e, ERRORS, "Не удалось сменить канал уведомлений"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" sx={{ mb: 1 }}>
          Уведомления
        </Typography>

        <Typography color="text.secondary" sx={{ mb: 2 }}>
          Куда присылать результаты автобалансировки и напоминания о событиях по
          облигациям.
        </Typography>

        {!profile.telegramLinked && !profile.email && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Нет ни одного канала — привяжите Telegram или добавьте почту.
          </Alert>
        )}

        <FormControl>
          <RadioGroup
            value={profile.notificationChannel}
            onChange={(e) => handleChange(e.target.value as NotificationChannel)}
          >
            {CHANNELS.map((channel) => (
              <FormControlLabel
                key={channel}
                value={channel}
                control={<Radio />}
                disabled={busy || unavailable(channel)}
                label={
                  NOTIFICATION_CHANNEL_LABELS[channel] +
                  (unavailable(channel) ? " — канал недоступен" : "")
                }
              />
            ))}
          </RadioGroup>
        </FormControl>
      </CardContent>
    </Card>
  );
}
