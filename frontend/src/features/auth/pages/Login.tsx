import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  Box,
  TextField,
  Button,
  Typography,
  Card,
  CardContent,
  Snackbar,
  Alert,
  Tabs,
  Tab,
} from "@mui/material";

import { useAuth } from "../../../app/AuthContext";

import {
  login as apiLogin,
  register as apiRegister,
  confirmEmail,
  resendCode,
} from "../api/client";
import { buttonStyles } from "../../../shared/theme/buttons";
import { errorDetail, errorMessage } from "../../../shared/utils/errors";

type Mode = "login" | "register";
type Step = "form" | "confirm";

const RESEND_COOLDOWN_SECONDS = 60;

const ERROR_MESSAGES: Record<string, string> = {
  email_already_registered: "Эта почта уже зарегистрирована",
  email_not_verified: "Почта не подтверждена — введите код из письма",
  invalid_code: "Неверный код",
  code_expired: "Код истёк, запросите новый",
  too_many_attempts: "Слишком много попыток — запросите новый код",
  resend_cooldown: "Код уже отправлен, подождите минуту",
  email_send_failed: "Не удалось отправить письмо, попробуйте позже",
};

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();

  // После входа возвращаем на страницу, с которой пришли (например,
  // диплинк привязки Telegram /link-telegram?code=…).
  const from = location.state?.from
    ? `${location.state.from.pathname}${location.state.from.search ?? ""}`
    : "/";

  const [mode, setMode] = useState<Mode>("login");
  const [step, setStep] = useState<Step>("form");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);

  useEffect(() => {
    if (resendCooldown <= 0) return;

    const timer = setTimeout(
      () => setResendCooldown((seconds) => seconds - 1),
      1000
    );

    return () => clearTimeout(timer);
  }, [resendCooldown]);

  const switchMode = (newMode: Mode) => {
    setMode(newMode);
    setStep("form");
    setCode("");
    setError("");
  };

  const handleLogin = async () => {
    setLoading(true);
    try {
      const res = await apiLogin(email, password);

      login(res.accessToken);

      navigate(from);
    } catch (e) {
      if (errorDetail(e) === "email_not_verified") {
        // Регистрацию начали, но почту не подтвердили — ведём на ввод кода.
        setMode("register");
        setStep("confirm");
        setInfo("Почта не подтверждена. Запросите код и введите его.");
      } else {
        setError("Неверный логин или пароль");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async () => {
    if (password.length < 6) {
      setError("Пароль должен быть не короче 6 символов");
      return;
    }

    setLoading(true);
    try {
      await apiRegister(email, password);

      setStep("confirm");
      setResendCooldown(RESEND_COOLDOWN_SECONDS);
      setInfo("Мы отправили код подтверждения на вашу почту");
    } catch (e) {
      setError(errorMessage(e, ERROR_MESSAGES, "Не удалось зарегистрироваться"));
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    setLoading(true);
    try {
      const res = await confirmEmail(email, code);

      login(res.accessToken);

      navigate(from);
    } catch (e) {
      setError(errorMessage(e, ERROR_MESSAGES, "Не удалось подтвердить почту"));
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setLoading(true);
    try {
      await resendCode(email);

      setResendCooldown(RESEND_COOLDOWN_SECONDS);
      setInfo("Код отправлен ещё раз");
    } catch (e) {
      setError(errorMessage(e, ERROR_MESSAGES, "Не удалось отправить код"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{
      display:"flex",
      justifyContent:"center",
      alignItems:"center",
      height:"100vh"
     }}
    >
      <Card sx={{ width: 400 }}>
        <CardContent>
          <Typography variant="h5" sx={{ mb: 2 }}>
            ShadowTrader
          </Typography>

          <Tabs
            value={mode}
            onChange={(_, newMode: Mode) => switchMode(newMode)}
            sx={{ mb: 2 }}
            variant="fullWidth"
          >
            <Tab label="Войти" value="login" />
            <Tab label="Регистрация" value="register" />
          </Tabs>

          {step === "form" && (
            <>
              <TextField
                fullWidth
                label="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                sx={{ mb: 2 }}
              />

              <TextField
                fullWidth
                label="Пароль"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                helperText={mode === "register" ? "Минимум 6 символов" : undefined}
                sx={{ mb: 2 }}
              />

              {mode === "login" ? (
                <Button fullWidth sx={buttonStyles} disabled={loading} onClick={handleLogin}>
                  Войти
                </Button>
              ) : (
                <Button fullWidth sx={buttonStyles} disabled={loading} onClick={handleRegister}>
                  Зарегистрироваться
                </Button>
              )}
            </>
          )}

          {step === "confirm" && (
            <>
              <Typography variant="body2" sx={{ mb: 2 }}>
                Введите код из письма, отправленного на {email}
              </Typography>

              <TextField
                fullWidth
                label="Код подтверждения"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                sx={{ mb: 2 }}
              />

              <Button
                fullWidth
                sx={{ ...buttonStyles, mb: 1 }}
                disabled={loading || !code}
                onClick={handleConfirm}
              >
                Подтвердить
              </Button>

              <Button
                fullWidth
                disabled={loading || resendCooldown > 0}
                onClick={handleResend}
              >
                {resendCooldown > 0
                  ? `Отправить код ещё раз (${resendCooldown})`
                  : "Отправить код ещё раз"}
              </Button>

              <Button fullWidth disabled={loading} onClick={() => switchMode(mode)}>
                Назад
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    <Snackbar
      open={!!error}
      autoHideDuration={3000}
      onClose={() => setError("")}
    >
      <Alert severity="error">
        {error}
      </Alert>
    </Snackbar>
    <Snackbar
      open={!!info}
      autoHideDuration={3000}
      onClose={() => setInfo("")}
    >
      <Alert severity="info">
        {info}
      </Alert>
    </Snackbar>
    </Box>
  );
}
