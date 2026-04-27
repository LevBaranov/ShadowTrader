import { useState } from "react";
import {
  Box,
  TextField,
  Button,
  Typography,
  Card,
  CardContent,
} from "@mui/material";

import { login } from "../services/auth";
import { buttonStyles } from "../theme/buttons";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleLogin = async () => {
    try {
      const res = await login(email, password);

      localStorage.setItem("token", res.access_token);

      window.location.href = "/";
    } catch (e) {
      alert("Ошибка логина");
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
    </Box>
  );
}