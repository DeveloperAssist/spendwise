import { useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { ApiError, api, tokenStore } from "./api";
import type { User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

interface TokenResponse {
  access_token: string;
  user: User;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(!!tokenStore.get());
  const [offline, setOffline] = useState(false);
  const queryClient = useQueryClient();

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
    queryClient.clear(); // never show the last user's data to the next one
  }, [queryClient]);

  useEffect(() => {
    if (tokenStore.get()) {
      api<User>("/api/auth/me")
        .then(setUser)
        .catch((e) => {
          if (e instanceof ApiError && e.status === 401) tokenStore.clear(); // expired or revoked
          else setOffline(true); // server unreachable: keep the token, offer a retry
        })
        .finally(() => setLoading(false));
    }
    window.addEventListener("spendwise:logout", logout);
    return () => window.removeEventListener("spendwise:logout", logout);
  }, [logout]);

  const accept = (r: TokenResponse) => {
    queryClient.clear();
    tokenStore.set(r.access_token);
    setUser(r.user);
  };

  const login = async (email: string, password: string) => {
    // OAuth2 password flow: a form with "username" and "password"
    accept(
      await api<TokenResponse>("/api/auth/login", {
        method: "POST",
        body: new URLSearchParams({ username: email, password }),
      }),
    );
  };

  const register = async (name: string, email: string, password: string) => {
    accept(await api<TokenResponse>("/api/auth/register", { method: "POST", json: { name, email, password } }));
  };

  if (offline) {
    return (
      <div className="grid min-h-screen place-items-center p-6 text-center">
        <div>
          <h1 className="text-xl font-bold">Can't reach SpendWise</h1>
          <p className="mt-2 text-sm text-slate-500">Check your connection, or that the server is running.</p>
          <button className="btn mt-5" onClick={() => location.reload()}>Try again</button>
        </div>
      </div>
    );
  }
  return <AuthContext.Provider value={{ user, loading, login, register, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
