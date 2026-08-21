import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Box,
  Button,
  Card,
  CardContent,
  Typography,
  Alert,
} from "@mui/material";

import { confirmTelegramLink } from "../../../shared/api/telegram";
import { buttonStyles } from "../../../shared/theme/buttons";
import { errorMessage } from "../../../shared/utils/errors";

const ERROR_MESSAGES: Record<string, string> = {
  invalid_code: "Код не найден или истёк. Запросите новый код у бота.",
  telegram_already_linked:
    "Этот Telegram-аккаунт уже привязан к другой учётке (или к вашей учётке уже привязан Telegram).",
};

export default function LinkTelegram() {
  const [searchParams] = useSearchParams();
  const code = searchParams.get("code") ?? "";

  const [status, setStatus] = useState<"idle" | "loading" | "done">("idle");
  const [error, setError] = useState("");

  const handleConfirm = async () => {
    setStatus("loading");
    setError("");
    try {
      await confirmTelegramLink(code);
      setStatus("done");
    } catch (e) {
      setStatus("idle");
      setError(
        errorMessage(e, ERROR_MESSAGES, "Не удалось привязать Telegram, попробуйте позже")
      );
    }
  };

  return (
    <Box sx={{
      display: "flex",
      justifyContent: "center",
      alignItems: "center",
      height: "100vh",
    }}
    >
      <Card sx={{ width: 400 }}>
        <CardContent>
          <Typography variant="h5" sx={{ mb: 2 }}>
            Привязка Telegram
          </Typography>

          {!code && (
            <Alert severity="warning">
              В ссылке нет кода привязки. Запросите ссылку у бота ещё раз.
            </Alert>
          )}

          {code && status !== "done" && (
            <>
              <Typography variant="body1" sx={{ mb: 2 }}>
                Привязать Telegram-аккаунт к вашей учётке? После привязки бот
                получит доступ к вашим стратегиям.
              </Typography>

              {error && (
                <Alert severity="error" sx={{ mb: 2 }}>
                  {error}
                </Alert>
              )}

              <Button
                fullWidth
                sx={buttonStyles}
                disabled={status === "loading"}
                onClick={handleConfirm}
              >
                Привязать
              </Button>
            </>
          )}

          {status === "done" && (
            <>
              <Alert severity="success" sx={{ mb: 2 }}>
                Telegram привязан. Вернитесь в чат с ботом — он уже готов к работе.
              </Alert>
              <Button fullWidth component={Link} to="/">
                На главную
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}
