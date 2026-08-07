import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  TextField,
  Typography,
} from "@mui/material";

import { buttonStyles } from "../../../shared/theme/buttons";
import { errorMessage } from "../../../shared/utils/errors";

import { confirmTelegramLink, unlinkTelegram } from "../../../shared/api/telegram";
import type { UserProfile } from "../types/profile";

const ERRORS: Record<string, string> = {
  invalid_code: "Код не найден или истёк — запросите новый у бота",
  telegram_already_linked:
    "Этот Telegram уже привязан к другой учётке (или к вашей уже привязан Telegram)",
  telegram_not_linked: "Telegram не привязан",
  last_login_method:
    "Telegram — единственный способ входа, отвязать нельзя. Сначала добавьте почту с паролем",
};

type Props = {
  profile: UserProfile;
  onChanged: () => Promise<void> | void;
  onError: (message: string) => void;
  onInfo: (message: string) => void;
};

export default function TelegramSection({ profile, onChanged, onError, onInfo }: Props) {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);

  const handleLink = async () => {
    try {
      setBusy(true);

      await confirmTelegramLink(code.trim().toUpperCase());

      setCode("");
      await onChanged();
      onInfo("Telegram привязан");
    } catch (e) {
      console.error(e);

      onError(errorMessage(e, ERRORS, "Не удалось привязать Telegram"));
    } finally {
      setBusy(false);
    }
  };

  const handleUnlink = async () => {
    if (!window.confirm("Отвязать Telegram? Бот перестанет вас узнавать.")) {
      return;
    }

    try {
      setBusy(true);

      await unlinkTelegram();

      await onChanged();
      onInfo("Telegram отвязан");
    } catch (e) {
      console.error(e);

      onError(errorMessage(e, ERRORS, "Не удалось отвязать Telegram"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" sx={{ mb: 1 }}>
          Telegram
        </Typography>

        {profile.telegramLinked ? (
          <>
            <Typography color="text.secondary" sx={{ mb: 2 }}>
              Привязан — бот доступен как второй интерфейс управления.
            </Typography>

            <Button onClick={handleUnlink} disabled={busy}>
              Отвязать
            </Button>
          </>
        ) : (
          <>
            <Alert severity="info" sx={{ mb: 2 }}>
              Отправьте боту /start, выберите «У меня есть аккаунт на вебе» и
              введите здесь полученный код. Код действует 10 минут.
            </Alert>

            <Box sx={{ display: "flex", gap: 1, alignItems: "center", flexWrap: "wrap" }}>
              <TextField
                label="Код из бота"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                sx={{ minWidth: 200 }}
              />

              <Button
                sx={buttonStyles}
                onClick={handleLink}
                disabled={busy || !code.trim()}
              >
                Привязать
              </Button>
            </Box>
          </>
        )}
      </CardContent>
    </Card>
  );
}
