"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { AlertCircle, CheckCircle2, Eye, EyeOff, Loader2 } from "lucide-react";

import { Label } from "@/components/ui/label";
import { Link } from "@/i18n/navigation";
import { LocaleSwitcher } from "@/components/i18n/LocaleSwitcher";
import { validatePassword } from "@/lib/validators";
import { getApiBase } from "@/lib/env";

function ResetPasswordContent() {
  const t = useTranslations("auth.resetPassword");
  const tc = useTranslations("common");
  const params = useSearchParams();
  const token = params.get("token") || "";

  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [pwdErr, setPwdErr] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!token) {
    return (
      <div className="text-center space-y-4">
        <AlertCircle className="mx-auto h-10 w-10 text-red-400" />
        <p className="text-sm text-gray-600">{t("invalid_link")}</p>
        <Link
          href="/forgot-password"
          className="inline-block text-sm font-semibold text-[#FF6B35] hover:text-[#e05a25]"
        >
          {t("request_again")}
        </Link>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const err = validatePassword(password);
    if (err) {
      setPwdErr(err);
      return;
    }
    setPwdErr(null);
    setError(null);
    setSubmitting(true);

    try {
      const lang = typeof document !== "undefined" ? document.documentElement.lang || "en" : "en";
      const fd = new FormData();
      fd.append("token", token);
      fd.append("new_password", password);
      const res = await fetch(`${getApiBase()}/api/v1/auth/reset-password`, {
        method: "POST",
        headers: { "Accept-Language": lang },
        body: fd,
      });
      const json = await res.json().catch(() => null);
      if (!res.ok) {
        setError(json?.message || json?.errors?.[0]?.message || t("error_generic"));
      } else {
        setDone(true);
      }
    } catch {
      setError(t("error_network"));
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <div className="space-y-5 text-center">
        <CheckCircle2 className="mx-auto h-12 w-12 text-[#10B981]" />
        <div>
          <h2 className="text-lg font-bold text-gray-900">{t("success_title")}</h2>
          <p className="mt-2 text-sm text-gray-500">{t("success_desc")}</p>
        </div>
        <Link
          href="/login"
          className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-[#0D4D4D] px-8 text-sm font-semibold text-white shadow-sm transition-all hover:bg-[#0a3d3d]"
        >
          {t("go_login")}
        </Link>
      </div>
    );
  }

  return (
    <>
      <div className="mb-6 text-center">
        <h2 className="text-xl font-bold text-gray-900">{t("title")}</h2>
        <p className="mt-2 text-sm text-gray-500">{t("subtitle")}</p>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2.5 rounded-lg border-l-4 border-red-500 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="password" className="text-sm font-semibold text-gray-700">
            {t("new_password")}
          </Label>
          <div className="relative">
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                if (pwdErr) setPwdErr(null);
              }}
              onBlur={() => {
                if (password) setPwdErr(validatePassword(password));
              }}
              autoComplete="new-password"
              className={
                "h-11 w-full rounded-lg border bg-white px-3 pr-12 text-sm text-gray-800 placeholder-gray-400 transition-all focus:outline-none focus:ring-2 " +
                (pwdErr
                  ? "border-red-400 focus:border-red-500 focus:ring-red-500/15"
                  : "border-gray-200 focus:border-[#0D4D4D] focus:ring-[#0D4D4D]/15")
              }
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              tabIndex={-1}
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          {pwdErr && <p className="text-xs text-red-500">{pwdErr}</p>}
          <p className="mt-1 text-[11px] text-gray-400">{t("pwd_hint")}</p>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#0D4D4D] text-sm font-semibold text-white shadow-sm transition-all hover:bg-[#0a3d3d] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-70"
        >
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              {t("submitting")}
            </>
          ) : (
            t("submit")
          )}
        </button>
      </form>

      <div className="mt-6 text-center">
        <Link
          href="/login"
          className="text-sm font-semibold text-[#FF6B35] transition-colors hover:text-[#e05a25]"
        >
          {t("back_to_login")}
        </Link>
      </div>

      <div className="mt-3 flex items-center justify-center gap-3">
        <Link href="/" className="text-xs text-gray-400 transition-colors hover:text-gray-600">
          {tc("back_to_home")}
        </Link>
        <span className="text-xs text-gray-300">|</span>
        <LocaleSwitcher variant="full" />
      </div>
    </>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-[#0D4D4D]" />
        </div>
      }
    >
      <ResetPasswordContent />
    </Suspense>
  );
}
