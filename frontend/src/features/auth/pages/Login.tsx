import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  TextField,
  Button,
  Typography,
  Card,
  CardContent,
  Snackbar,
  Alert,
} from "@mui/material";

import { useAuth } from "../../../app/AuthContext";

import { login as apiLogin } from "../api/client";
import { buttonStyles } from "../../../shared/theme/buttons";

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleLogin = async () => {
    try {
      const res = await apiLogin(email, password);

      login(res.accessToken);

      navigate("/");
    } catch (e) {
      setError("Неверный логин или пароль");
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
            sx={{ mb: 2 }}
          />

          <Button fullWidth sx={buttonStyles} onClick={handleLogin}>
            Войти
          </Button>
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
    </Box>
  );
}