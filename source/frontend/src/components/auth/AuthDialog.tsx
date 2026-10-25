"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { uiText } from "@/shared/i18n/ru";
import type { UserRole } from "@/shared/types/auth";

type AuthMode = "login" | "register";

interface AuthDialogProps {
  open: boolean;
  busy: boolean;
  error: string | null;
  onClose: () => void;
  onLogin: (email: string, password: string) => Promise<void>;
  onRegister: (input: {
    email: string;
    username: string;
    password: string;
    role: UserRole;
  }) => Promise<string>;
}

export function AuthDialog({
  open,
  busy,
  error,
  onClose,
  onLogin,
  onRegister,
}: AuthDialogProps) {
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [role, setRole] = useState<UserRole>("user");
  const [info, setInfo] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  if (!open) {
    return null;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLocalError(null);
    setInfo(null);
    try {
      if (mode === "login") {
        await onLogin(email.trim(), password);
        onClose();
        return;
      }
      if (password !== passwordConfirm) {
        setLocalError(uiText.authPasswordMismatch);
        return;
      }
      const message = await onRegister({
        email: email.trim(),
        username: username.trim(),
        password,
        role,
      });
      setInfo(message);
      setMode("login");
      setPassword("");
      setPasswordConfirm("");
    } catch {
      // ошибка уже в props.error / set в хуке
    }
  }

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/55 p-4">
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-md rounded-xl border border-zinc-700 bg-zinc-950 shadow-2xl"
      >
        <div className="flex items-center justify-between gap-3 border-b border-zinc-800 px-4 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <Link
              href="/"
              className="inline-flex shrink-0 items-center rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-500"
              aria-label={uiText.appName}
              title={uiText.appName}
              onClick={onClose}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/brand-logo.png"
                alt={uiText.appName}
                className="h-7 w-auto max-w-[160px] object-contain object-left"
              />
            </Link>
            <h2 className="truncate text-sm font-semibold text-zinc-100">
              {mode === "login" ? uiText.authTitleLogin : uiText.authTitleRegister}
            </h2>
          </div>
          <button
            type="button"
            className="rounded border border-zinc-700 px-2 py-0.5 text-[10px] text-zinc-300 hover:bg-zinc-800"
            onClick={onClose}
          >
            {uiText.authClose}
          </button>
        </div>
        <form className="space-y-3 p-4" onSubmit={(event) => void submit(event)}>
          <Field
            label={uiText.authEmail}
            type="email"
            autoComplete="email"
            value={email}
            onChange={setEmail}
            required
          />
          {mode === "register" ? (
            <Field
              label={uiText.authUsername}
              type="text"
              autoComplete="username"
              value={username}
              onChange={setUsername}
              required
              hint="3-32 символа: латиница, цифры, _"
            />
          ) : null}
          <Field
            label={uiText.authPassword}
            type="password"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            value={password}
            onChange={setPassword}
            required
          />
          {mode === "register" ? (
            <>
              <Field
                label={uiText.authPasswordConfirm}
                type="password"
                autoComplete="new-password"
                value={passwordConfirm}
                onChange={setPasswordConfirm}
                required
              />
              <label className="block space-y-1 text-xs text-zinc-400">
                <span>{uiText.authRole}</span>
                <select
                  className="w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm text-zinc-100"
                  value={role}
                  onChange={(event) => setRole(event.target.value as UserRole)}
                >
                  <option value="user">{uiText.authRoleUser}</option>
                  <option value="admin">{uiText.authRoleAdmin}</option>
                </select>
                <span className="text-[10px] text-amber-300/90">{uiText.authRoleDevHint}</span>
              </label>
            </>
          ) : null}

          {localError || error ? (
            <p className="rounded border border-red-900/60 bg-red-950/40 px-2 py-1.5 text-xs text-red-200">
              {localError ?? error}
            </p>
          ) : null}
          {info ? (
            <p className="rounded border border-emerald-900/50 bg-emerald-950/30 px-2 py-1.5 text-xs text-emerald-100">
              {info}
            </p>
          ) : null}

          <button
            type="submit"
            disabled={busy}
            className="w-full rounded border border-sky-700 bg-sky-950/50 px-3 py-2 text-sm text-sky-100 hover:bg-sky-900/40 disabled:opacity-50"
          >
            {mode === "login" ? uiText.authSubmitLogin : uiText.authSubmitRegister}
          </button>
          <button
            type="button"
            className="w-full text-center text-xs text-zinc-400 underline-offset-2 hover:text-zinc-200 hover:underline"
            onClick={() => {
              setMode((value) => (value === "login" ? "register" : "login"));
              setLocalError(null);
              setInfo(null);
            }}
          >
            {mode === "login" ? uiText.authSwitchToRegister : uiText.authSwitchToLogin}
          </button>
        </form>
      </div>
    </div>
  );
}

function Field({
  label,
  type,
  value,
  onChange,
  required,
  autoComplete,
  hint,
}: {
  label: string;
  type: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  autoComplete?: string;
  hint?: string;
}) {
  return (
    <label className="block space-y-1 text-xs text-zinc-400">
      <span>{label}</span>
      <input
        type={type}
        value={value}
        required={required}
        autoComplete={autoComplete}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm text-zinc-100"
      />
      {hint ? <span className="text-[10px] text-zinc-500">{hint}</span> : null}
    </label>
  );
}
