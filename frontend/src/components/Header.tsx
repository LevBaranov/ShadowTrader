import { Box, Button } from "@mui/material";
import { useLocation, useNavigate } from "react-router-dom";

export default function Header() {
  const nav = useNavigate();
  const location = useLocation();

  const isActive = (path: string) => location.pathname === path;

  return (
    <Box
      display="flex"
      justifyContent="flex-end"
      mb={3}
    >
      <Button
        variant={isActive("/") ? "contained" : "outlined"}
        onClick={() => nav("/")}
        sx={{
          mr: 1,
          color: "#444",
          borderColor: "#888",
          background: isActive("/") ? "#bbb" : "transparent",
        }}
      >
        Балансировка
      </Button>

      <Button
        variant={isActive("/bonds") ? "contained" : "outlined"}
        onClick={() => nav("/bonds")}
        sx={{
          color: "#444",
          borderColor: "#888",
          background: isActive("/bonds") ? "#bbb" : "transparent",
        }}
      >
        Облигации
      </Button>
    </Box>
  );
}