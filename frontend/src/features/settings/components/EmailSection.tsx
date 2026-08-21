import { useEffect, useState } from "react";
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
import { errorDetail, errorMessage, errorStatus } from "../../../shared/utils/errors";

import {
  cancelEmailChange,
  confirmEmailChange,
  requestEmailChange,
  resendEmailCode,
} from "../api/client";
import type { UserProfile } from "../types/profile";

const RESEND_COOLDOWN_SECONDS = 60;
const MIN_PASSWORD_LENGTH = 6;

const ERRORS: Record<string, string> = {
  email_already_registered: "Эта почта уже занята другой учётной записью",
  email_unchanged: "Это и есть ваша текущая почта",
  invalid_code: "Неверный код",
  code_expired: "Код истёк, запросите новый",
  too_many_attempts: "Слишком много попыток — запросите новый код",
  resend_cooldown: "Код уже отправлен, подождите минуту",
  email_send_failed: "Не удалось отправить письмо, попробуйте позже",
  no_pending_email: "Смена почты не начата",
};

type Props = {
  profile: UserProfile;
  onChanged: () => Promise<void> | void;
  onError: (message: string) => void;
  onInfo: (message: string) => void;
};

export default function EmailSection({ profile, onChanged, onError, onInfo }: Props) {
  // Пользователь без входа по почте добавляет её вместе с паролем.
  const isAdding = !profile.email;

  const [editing, setEditing] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  // Незавершённая смена почты переживает перезагрузку страницы: код уже выдан.
  const awaitingCode = !!profile.pendingEmail;

  useEffect(() => {
    if (cooldown <= 0) return;

    const timer = setTimeout(() => setCooldown((seconds) => seconds - 1), 1000);

    return () => clearTimeout(timer);
  }, [cooldown]);

  const reset = () => {
    setEditing(false);
    setEmail("");
    setPassword("");
    setCode("");
  };

  const handleRequest = async () => {
    if (isAdding && password.length < MIN_PASSWORD_LENGTH) {
      onError(`Пароль должен быть не короче ${MIN_PASSWORD_LENGTH} символов`);
      return;
    }

    try {
      setBusy(true);

      await requestEmailChange(email, isAdding ? password : undefined);

      setPassword("");
      setCooldown(RESEND_COOLDOWN_SECONDS);
      await onChanged();
      onInfo("Код подтверждения отправлен на новый адрес");
    } catch (e) {
      console.error(e);

      if (errorStatus(e) === 422 && !errorDetail(e)) {
        onError("Проверьте адрес почты");
        return;
      }
      onError(errorMessage(e, ERRORS, "Не удалось начать смену почты"));
    } finally {
      setBusy(false);
    }
  };

  const handleConfirm = async () => {
    try {
      setBusy(true);

      await confirmEmailChange(code);

      reset();
      await onChanged();
      onInfo("Почта обновлена");
    } catch (e) {
      console.error(e);

      onError(errorMessage(e, ERRORS, "Не удалось подтвердить почту"));
    } finally {
      setBusy(false);
    }
  };

  const handleResend = async () => {
    try {
      setBusy(true);

      await resendEmailCode();

      setCooldown(RESEND_COOLDOWN_SECONDS);
      onInfo("Код отправлен ещё раз");
    } catch (e) {
      console.error(e);

      onError(errorMessage(e, ERRORS, "Не удалось отправить код"));
    } finally {
      setBusy(false);
    }
  };

  const handleCancel = async () => {
    try {
      setBusy(true);

      await cancelEmailChange();

      reset();
      await onChanged();
      onInfo("Смена почты отменена");
    } catch (e) {
      console.error(e);

      onError(errorMessage(e, ERRORS, "Не удалось отменить смену почты"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" sx={{ mb: 1 }}>
          Почта
        </Typography>

        <Typography color="text.secondary" sx={{ mb: 2 }}>
          {profile.email ?? "Не задана — вход только через Telegram"}
        </Typography>

        {awaitingCode ? (
          <>
            <Alert severity="info" sx={{ mb: 2 }}>
              На адрес {profile.pendingEmail} отправлен код подтверждения. Пока
              код не подтверждён, вход работает по прежним данным.
            </Alert>

            <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", alignItems: "center" }}>
              <TextField
                label="Код из письма"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                sx={{ minWidth: 200 }}
              />

              <Button
                sx={buttonStyles}
                onClick={handleConfirm}
                disabled={busy || !code}
              >
                Подтвердить
              </Button>

              <Button onClick={handleResend} disabled={busy || cooldown > 0}>
                {cooldown > 0
                  ? `Отправить ещё раз (${cooldown})`
                  : "Отправить ещё раз"}
              </Button>

              <Button color="inherit" onClick={handleCancel} disabled={busy}>
                Отменить
              </Button>
            </Box>
          </>
        ) : editing ? (
          <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", alignItems: "center" }}>
            <TextField
              label="Новая почта"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              sx={{ minWidth: 260 }}
            />

            {isAdding && (
              <TextField
                label="Пароль"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                helperText={`Минимум ${MIN_PASSWORD_LENGTH} символов`}
                sx={{ minWidth: 200 }}
              />
            )}

            <Button
              sx={buttonStyles}
              onClick={handleRequest}
              disabled={busy || !email}
            >
              Отправить код
            </Button>

            <Button color="inherit" onClick={reset} disabled={busy}>
              Отмена
            </Button>
          </Box>
        ) : (
          <Button sx={buttonStyles} onClick={() => setEditing(true)}>
            {isAdding ? "Добавить почту" : "Изменить почту"}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
