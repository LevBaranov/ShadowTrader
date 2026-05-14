import { Routes, Route, Navigate } from "react-router-dom";
import Rebalance from "../features/rebalance/pages/Rebalance";
import Bonds from "../features/bonds/pages/Bonds";
import Login from "../features/auth/pages/Login";
import MainLayout from "./MainLayout";
import { useAuth } from "./AuthContext";


export default function Router() {
  const { isAuthenticated } = useAuth();

  return (
    <Routes>
      <Route
        element={
          isAuthenticated ? (
            <MainLayout />
          ) : (
            <Navigate to="/login" />
          )
        }
      >
        <Route path="/" element={<Rebalance />} />
        <Route path="/bonds" element={<Bonds />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Route>

      <Route
        path="/login"
        element={
          isAuthenticated ? <Navigate to="/" /> : <Login />
        }
      />
    </Routes>
  );
}