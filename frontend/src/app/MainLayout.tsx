import { Alert, Container } from "@mui/material";
import { Outlet } from "react-router-dom";
import Header from "../shared/components/Header";

export default function MainLayout() {
  return (
    <Container maxWidth="lg">
      <Alert severity="warning" sx={{ mt: 2, mb: 2 }}>
        Бот Telegram работает нестабильно. Рекомендуем получать уведомления на
        почту, а для управления пока воспользоваться текущим веб-интерфейсом.
      </Alert>
      <Header />
      <Outlet />
    </Container>
  );
}
