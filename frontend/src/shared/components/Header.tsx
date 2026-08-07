import { Box, Button } from "@mui/material";
import { useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../../app/AuthContext";

const NAV_ITEMS = [
  { path: "/", label: "Отслеживание" },
  { path: "/bonds", label: "Облигации" },
  { path: "/settings", label: "Настройки" },
];

export default function Header() {
  const nav = useNavigate();
  const location = useLocation();
  const { logout } = useAuth();

  const isActive = (path: string) => location.pathname === path;

  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: "flex-end",
        gap: 1,
        mb: 3,
      }}
    >
      {NAV_ITEMS.map((item) => (
        <Button
          key={item.path}
          variant={isActive(item.path) ? "contained" : "outlined"}
          onClick={() => nav(item.path)}
          sx={{
            color: "#444",
            borderColor: "#888",
            background: isActive(item.path) ? "#bbb" : "transparent",
          }}
        >
          {item.label}
        </Button>
      ))}

      <Button onClick={logout} sx={{ color: "#444" }}>
        Выйти
      </Button>
    </Box>
  );
}
