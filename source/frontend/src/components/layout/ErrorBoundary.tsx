"use client";

import Link from "next/link";
import { Component, type ErrorInfo, type ReactNode } from "react";

import { uiText } from "@/shared/i18n/ru";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  message: string;
}

/** Ловит падения React, чтобы вкладка не уходила в белый экран/перезагрузку. */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, message: "" };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return {
      hasError: true,
      message: error.message || uiText.appCrashFallback,
    };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("workspace_ui_crash", error.message, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-screen flex-col items-center justify-center gap-3 bg-zinc-950 px-6 text-center text-zinc-200">
          <Link
            href="/"
            className="inline-flex items-center rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-500"
            aria-label={uiText.appName}
            title={uiText.appName}
            onClick={() => this.setState({ hasError: false, message: "" })}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/brand-logo.png"
              alt={uiText.appName}
              className="h-10 w-auto max-w-[280px] object-contain"
            />
          </Link>
          <p className="text-sm font-medium">{uiText.appCrashTitle}</p>
          <p className="max-w-lg text-xs text-zinc-500">{this.state.message}</p>
          <button
            type="button"
            className="rounded border border-zinc-700 px-3 py-1.5 text-xs hover:bg-zinc-900"
            onClick={() => this.setState({ hasError: false, message: "" })}
          >
            {uiText.appCrashRetry}
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
