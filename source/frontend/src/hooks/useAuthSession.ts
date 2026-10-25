"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiClientError } from "@/shared/api/client";
import {
  authChangePassword,
  authLogin,
  authLogout,
  authMe,
  authRegister,
  authUpdateProfile,
} from "@/shared/api/auth";
import type { AuthUser, UserRole } from "@/shared/types/auth";

export type AuthStatus = "loading" | "anonymous" | "authenticated";

export function useAuthSession() {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const me = await authMe();
      setUser(me);
      setStatus("authenticated");
      setError(null);
    } catch (err) {
      setUser(null);
      setStatus("anonymous");
      if (err instanceof ApiClientError && err.statusCode !== 401) {
        setError(err.message);
      }
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function login(email: string, password: string) {
    setBusy(true);
    setError(null);
    try {
      const result = await authLogin({ email, password });
      setUser(result.user);
      setStatus("authenticated");
      return result.user;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Ошибка входа";
      setError(message);
      throw err;
    } finally {
      setBusy(false);
    }
  }

  async function register(input: {
    email: string;
    username: string;
    password: string;
    role: UserRole;
  }) {
    setBusy(true);
    setError(null);
    try {
      return await authRegister(input);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Ошибка регистрации";
      setError(message);
      throw err;
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    setBusy(true);
    setError(null);
    try {
      await authLogout();
    } catch {
      // сессия могла уже истечь
    } finally {
      setUser(null);
      setStatus("anonymous");
      setBusy(false);
    }
  }

  async function changePassword(currentPassword: string, newPassword: string) {
    setBusy(true);
    setError(null);
    try {
      const result = await authChangePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setUser(result.user);
      setStatus("authenticated");
      return result.user;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Не удалось сменить пароль";
      setError(message);
      throw err;
    } finally {
      setBusy(false);
    }
  }

  async function updateRole(role: UserRole) {
    setBusy(true);
    setError(null);
    try {
      const next = await authUpdateProfile({ role });
      setUser(next);
      return next;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Не удалось обновить профиль";
      setError(message);
      throw err;
    } finally {
      setBusy(false);
    }
  }

  return {
    status,
    user,
    busy,
    error,
    setError,
    refresh,
    login,
    register,
    logout,
    changePassword,
    updateRole,
  };
}
