import api from "../../../shared/api/client";
import type { LoginResponse } from "../types/login";

export const login = async (email: string, password: string) => {
  const res = await api.post<LoginResponse>("/auth/login", {
    email,
    password,
  });

  return res.data;
};

export const register = async (email: string, password: string) => {
  await api.post("/auth/register", {
    email,
    password,
  });
};

export const confirmEmail = async (email: string, code: string) => {
  const res = await api.post<LoginResponse>("/auth/register/confirm", {
    email,
    code,
  });

  return res.data;
};

export const resendCode = async (email: string) => {
  await api.post("/auth/register/resend", {
    email,
  });
};
