import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { uiText } from "@/shared/i18n/ru";
import { UI_THEME_STORAGE_KEY } from "@/shared/theme/uiTheme";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

/** Всегда ПК-раскладка: на телефонах/планшетах браузер рисует desktop-ширину. */
export const viewport: Viewport = {
  width: 1280,
  initialScale: 1,
};

export const metadata: Metadata = {
  title: uiText.appName,
  description: "Визуальная среда для анализа и преобразования Java-кода (Frontend Lite).",
};

/** Анти-мигание темы до гидрации React. */
const themeBootScript = `
(function () {
  try {
    var key = ${JSON.stringify(UI_THEME_STORAGE_KEY)};
    var pref = localStorage.getItem(key) || "dark";
    var allowed = { dark:1, light:1, system:1, neon:1, terminal:1, galactic:1 };
    if (!allowed[pref]) pref = "dark";
    var resolved = pref;
    if (pref === "system") {
      resolved = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    }
    document.documentElement.setAttribute("data-theme", resolved);
    document.documentElement.setAttribute("data-theme-pref", pref);
    document.documentElement.style.colorScheme = resolved === "light" ? "light" : "dark";
  } catch (e) {}
})();
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootScript }} />
      </head>
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>{children}</body>
    </html>
  );
}
