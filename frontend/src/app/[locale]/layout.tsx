import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import { AuthProvider } from "@/components/auth/AuthProvider";
import { ToastProvider } from "@/components/ui/Toast";
import { BRAND } from "@/config/brand";

export const metadata: Metadata = {
  title: BRAND.fullTitle,
  description: BRAND.description,
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/icon.png", type: "image/png", sizes: "512x512" },
      { url: BRAND.logoIcon, type: "image/png", sizes: "512x512" },
    ],
    shortcut: "/favicon.ico",
    apple: BRAND.logoIcon,
  },
};

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  if (!routing.locales.includes(locale as (typeof routing.locales)[number])) {
    notFound();
  }

  const messages = await getMessages();

  return (
    <html lang={locale}>
      <body>
        <NextIntlClientProvider messages={messages}>
          <AuthProvider><ToastProvider>{children}</ToastProvider></AuthProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
