import { create } from "zustand";
import { api } from "@/lib/api";
import type { User } from "@/types";

interface AuthState {
  token: string | null;
  user: User | null;
  _hydrated: boolean;
  setAuth: (token: string, user: User) => void;
  logout: () => void;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
}

export const useAuth = create<AuthState>((set, get) => ({
  token: null,
  user: null,
  _hydrated: false,

  setAuth: (token, user) => {
    localStorage.setItem("token", token);
    localStorage.setItem("user", JSON.stringify(user));
    set({ token, user });
  },

  logout: () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    set({ token: null, user: null });
  },

  login: async (username, password) => {
    const { access_token } = await api<{ access_token: string }>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });

    const user = await api<User>("/api/v1/auth/me", {
      token: access_token,
    });

    get().setAuth(access_token, user);
  },

  register: async (username, email, password) => {
    await api<User>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, email, password }),
    });
    await get().login(username, password);
  },
}));

// Hydrate from localStorage on client — runs once after store creation
if (typeof window !== "undefined") {
  const token = localStorage.getItem("token");
  const user = JSON.parse(localStorage.getItem("user") || "null");
  useAuth.setState({ token, user, _hydrated: true });
}
