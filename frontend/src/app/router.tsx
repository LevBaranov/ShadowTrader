import { Routes, Route, Navigate } from "react-router-dom";
import Rebalance from "../pages/Rebalance";
import Bonds from "../pages/Bonds";
import Login from "../pages/Login";
import MainLayout from "./MainLayout";

const isAuth = () => !!localStorage.getItem("token");


export default function Router() {
  return (
    <Routes>
      {/* 🔒 приватные страницы */}
      <Route
        element={isAuth() ? <MainLayout /> : <Navigate to="/login" />}
      >
        <Route path="/" element={<Rebalance />} />
        <Route path="/bonds" element={<Bonds />} />

        {/* fallback */}
        <Route path="*" element={<Navigate to="/" />} />

      </Route>

      {/* 🔐 публичная */}
      <Route path="/login" element={<Login />} />
    </Routes>
  );
}