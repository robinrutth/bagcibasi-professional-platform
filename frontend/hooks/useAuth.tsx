"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { getCurrentUser, login as loginApi, logout as logoutApi, refreshToken as refreshTokenApi } from "@/lib/api/auth";
import { getAccessToken, getRefreshToken, getStoredUser, storeUser } from "@/lib/api/client";
import { getRoleFromJwt, type Role } from "@/lib/permissions";
import type { User } from "@/types";

type AuthContextValue = {
  user: User | null;
  isLoading: boolean;
  ready: boolean;
  isAuthenticated: boolean;
  role: Role | null;
  accessToken: string;
  refreshToken: string;
  login: (username: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  refresh: () => Promise<string>;
  updateUser: (user: User) => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState("");
  const [refreshTokenValue, setRefreshTokenValue] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    async function bootstrap() {
      const storedAccessToken = getAccessToken() ?? "";
      const storedRefreshToken = getRefreshToken() ?? "";
      const storedUser = getStoredUser<User>();

      if (!mounted) return;
      setAccessToken(storedAccessToken);
      setRefreshTokenValue(storedRefreshToken);
      setUser(storedUser);

      try {
        if (storedAccessToken) {
          const currentUser = await getCurrentUser();
          if (!mounted) return;
          setUser(currentUser);
        } else if (storedRefreshToken) {
          const nextToken = await refreshTokenApi();
          const currentUser = await getCurrentUser();
          if (!mounted) return;
          setAccessToken(nextToken);
          setRefreshTokenValue(getRefreshToken() ?? "");
          setUser(currentUser);
        }
      } catch {
        if (!mounted) return;
        setUser(null);
        setAccessToken("");
        setRefreshTokenValue("");
      } finally {
        if (mounted) setIsLoading(false);
      }
    }

    void bootstrap();
    return () => {
      mounted = false;
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const result = await loginApi(username, password);
    setUser(result.user);
    setAccessToken(result.access_token);
    setRefreshTokenValue(result.refresh_token);
    return result.user;
  }, []);

  const refresh = useCallback(async () => {
    const token = await refreshTokenApi();
    setAccessToken(token);
    setRefreshTokenValue(getRefreshToken() ?? "");
    const currentUser = await getCurrentUser();
    setUser(currentUser);
    return token;
  }, []);

  const logout = useCallback(async () => {
    await logoutApi();
    setUser(null);
    setAccessToken("");
    setRefreshTokenValue("");
  }, []);

  const updateUser = useCallback((nextUser: User) => {
    storeUser(nextUser);
    setUser(nextUser);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      ready: !isLoading,
      isAuthenticated: Boolean(accessToken && user),
      role: getRoleFromJwt(accessToken),
      accessToken,
      refreshToken: refreshTokenValue,
      login,
      logout,
      refresh,
      updateUser,
    }),
    [accessToken, isLoading, login, logout, refresh, refreshTokenValue, updateUser, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }
  return context;
}
