import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import Rebalance from "../features/rebalance/pages/Rebalance";
import Bonds from "../features/bonds/pages/Bonds";
import Settings from "../features/settings/pages/Settings";
import Login from "../features/auth/pages/Login";
import LinkTelegram from "../features/auth/pages/LinkTelegram";
import MainLayout from "./MainLayout";
import { useAuth } from "./AuthContext";


export default function Router() {
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  return (
    <Routes>
      <Route
        element={
          isAuthenticated ? (
            <MainLayout />
          ) : (
            <Navigate to="/login" state={{ from: location }} />
          )
        }
      >
        <Route path="/" element={<Rebalance />} />
        <Route path="/bonds" element={<Bonds />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Route>

      {/* Страница привязки Telegram: защищена, но без общего лейаута —
          пользователь приходит сюда по диплинку из бота. */}
      <Route
        path="/link-telegram"
        element={
          isAuthenticated ? (
            <LinkTelegram />
          ) : (
            <Navigate to="/login" state={{ from: location }} />
          )
        }
      />

      <Route
        path="/login"
        element={
          isAuthenticated ? <Navigate to="/" /> : <Login />
        }
      />
    </Routes>
  );
}
