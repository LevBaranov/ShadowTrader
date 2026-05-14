import api from "../../../shared/api/client";
import type { LoginResponse } from "../types/login";

export const login = async (email: string, password: string) => {
  const res = await api.post<LoginResponse>("/auth/login", {
    email,
    password,
  });

    return res.data;

};