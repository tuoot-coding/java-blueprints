"use client";

import Link from "next/link";
import { useState } from "react";

import { uiText } from "@/shared/i18n/ru";
import type { AuthUser, UserRole } from "@/shared/types/auth";

interface CabinetDialogProps {
  open: boolean;
  user: AuthUser;
  busy: boolean;
  error: string | null;
  onClose: () => void;
  onLogout: () => Promise<void>;
  onChangePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  onUpdateRole: (role: UserRole) => Promise<void>;
}

export function CabinetDialog({
  open,
  user,
  busy,
  error,
  onClose,
  onLogout,
  onChangePassword,
  onUpdateRole,
}: CabinetDialogProps) {
  const [role, setRole] = useState<UserRole>(user.role);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newPasswordConfirm, setNewPasswordConfirm] = useState("");
  const [info, setInfo] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/55 p-4">
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-lg rounded-xl border border-zinc-700 bg-zinc-950 shadow-2xl"
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
              {uiText.authTitleCabinet}
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

        <div className="space-y-4 p-4 text-sm text-zinc-300">
          <dl className="grid grid-cols-[7rem_1fr] gap-x-3 gap-y-2 text-xs">
            <dt className="text-zinc-500">{uiText.authEmail}</dt>
            <dd className="break-all text-zinc-100">{user.email}</dd>
            <dt className="text-zinc-500">{uiText.authUsername}</dt>
            <dd className="text-zinc-100">{user.username}</dd>
            <dt className="text-zinc-500">Email</dt>
            <dd className={user.email_verified ? "text-emerald-300" : "text-amber-300"}>
              {user.email_verified ? uiText.authEmailVerified : uiText.authEmailPending}
            </dd>
          </dl>

          <form
            className="space-y-2 rounded border border-zinc-800 bg-zinc-900/40 p-3"
            onSubmit={(event) => {
              event.preventDefault();
              setLocalError(null);
              setInfo(null);
              void onUpdateRole(role)
                .then(() => setInfo(uiText.authRoleSaved))
                .catch(() => undefined);
            }}
          >
            <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">
              {uiText.authRole}
            </p>
            <p className="text-[10px] text-amber-300/90">{uiText.authRoleDevHint}</p>
            <select
              className="w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm text-zinc-100"
              value={role}
              onChange={(event) => setRole(event.target.value as UserRole)}
            >
              <option value="user">{uiText.authRoleUser}</option>
              <option value="admin">{uiText.authRoleAdmin}</option>
            </select>
            <button
              type="submit"
              disabled={busy || role === user.role}
              className="rounded border border-zinc-600 px-2 py-1 text-[11px] text-zinc-200 hover:bg-zinc-800 disabled:opacity-50"
            >
              {uiText.authSaveRole}
            </button>
          </form>

          <form
            className="space-y-2 rounded border border-zinc-800 bg-zinc-900/40 p-3"
            onSubmit={(event) => {
              event.preventDefault();
              setLocalError(null);
              setInfo(null);
              if (newPassword !== newPasswordConfirm) {
                setLocalError(uiText.authPasswordMismatch);
                return;
              }
              void onChangePassword(currentPassword, newPassword)
                .then(() => {
                  setInfo(uiText.authChangePasswordOk);
                  setCurrentPassword("");
                  setNewPassword("");
                  setNewPasswordConfirm("");
                })
                .catch(() => undefined);
            }}
          >
            <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">
              {uiText.authChangePassword}
            </p>
            <input
              type="password"
              required
              placeholder={uiText.authCurrentPassword}
              autoComplete="current-password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              className="w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm text-zinc-100"
            />
            <input
              type="password"
              required
              placeholder={uiText.authNewPassword}
              autoComplete="new-password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              className="w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm text-zinc-100"
            />
            <input
              type="password"
              required
              placeholder={uiText.authPasswordConfirm}
              autoComplete="new-password"
              value={newPasswordConfirm}
              onChange={(event) => setNewPasswordConfirm(event.target.value)}
              className="w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm text-zinc-100"
            />
            <button
              type="submit"
              disabled={busy}
              className="rounded border border-sky-700 bg-sky-950/40 px-2 py-1 text-[11px] text-sky-100 hover:bg-sky-900/40 disabled:opacity-50"
            >
              {uiText.authChangePasswordSubmit}
            </button>
          </form>

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

          <div className="flex justify-end gap-2 border-t border-zinc-800 pt-3">
            <button
              type="button"
              disabled={busy}
              className="rounded border border-red-800 px-3 py-1.5 text-xs text-red-200 hover:bg-red-950/40 disabled:opacity-50"
              onClick={() => {
                void onLogout().then(() => onClose());
              }}
            >
              {uiText.actionLogout}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
