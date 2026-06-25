"use client";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AlertCircle, CheckCircle2, Eye, EyeOff, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";

import { Label } from "@/components/ui/label";
import { useLogin } from "@/hooks/useAuth";
import { ApiError } from "@/lib/api";
import { Link } from "@/i18n/navigation";
import { LocaleSwitcher } from "@/components/i18n/LocaleSwitcher";

const PHONE_REGIONS = [
  { code: "TZ" as const, dialCode: "+255", flag: "🇹🇿" },
  { code: "CN" as const, dialCode: "+86", flag: "🇨🇳" },
];

/** identifier 是否看起来像手机号(纯数字 ≥7 位或以 + 开头) */
function looksLikePhone(v: string): boolean {
  const s = v.trim();
  return s.startsWith("+") || (/^\d+$/.test(s) && s.length >= 7);
}

/** 根据号码自动推断国家码 */
function guessPhoneRegion(v: string): string {
  const s = v.trim();
  if (s.startsWith("+86")) return "CN";
  if (s.startsWith("+255")) return "TZ";
  // 纯数字 11 位且 1 开头 → 中国号
  if (/^1[3-9]\d{9}$/.test(s)) return "CN";
  return "TZ";
}

function LoginContent() {
  const t = useTranslations("auth.login");
  const tc = useTranslations("common");
  const params = useSearchParams();
  const justRegistered = params.get("registered") === "1";
  const [identifier, setIdentifier] = useState("");
  const [phoneRegion, setPhoneRegion] = useState("TZ");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [idErr, setIdErr] = useState<string | null>(null);
  const [pwdErr, setPwdErr] = useState<string | null>(null);
  const login = useLogin();

  const isPhone = looksLikePhone(identifier);

  // identifier 变化时自动推断国家码（含浏览器 autofill）
  useEffect(() => {
    if (isPhone) setPhoneRegion(guessPhoneRegion(identifier));
  }, [identifier, isPhone]);

  // 注册成功跳转过来时,自动填充刚才提交的凭证(sessionStorage,一次性消费)
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("prefill_login");
      if (!raw) return;
      sessionStorage.removeItem("prefill_login");
      const data = JSON.parse(raw) as { identifier?: string; password?: string };
      if (data.identifier) setIdentifier(data.identifier);
      if (data.password) setPassword(data.password);
    } catch {
      // JSON 解析失败或 sessionStorage 不可用 → 静默忽略,正常空白登录
    }
  }, []);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const ie = identifier ? null : t("identifier_required");
    const pe = password ? null : t("password_required");
    setIdErr(ie);
    setPwdErr(pe);
    if (ie || pe) {
      setError(ie ?? pe);
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await login(identifier, password, isPhone ? phoneRegion : undefined);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 429) {
          setError(t("error_rate_limit"));
        } else if (err.status === 401) {
          setError(t("error_invalid_credentials"));
        } else {
          setError(err.message || t("error_unknown"));
        }
      } else {
        setError(t("error_network"));
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <div className="mb-7 text-center">
        <h2 className="text-xl font-bold text-gray-900">{t("title")}</h2>
      </div>

      {justRegistered && (
        <div className="mb-5 flex items-center gap-2.5 rounded-lg border-l-4 border-[#10B981] bg-[#10B981]/10 px-4 py-3 text-sm text-[#047857]">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{t("registered_success")}</span>
        </div>
      )}

      {error && (
        <div className="mb-5 flex items-center gap-2.5 rounded-lg border-l-4 border-red-500 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={onSubmit} className="space-y-5" noValidate>
        <div className="space-y-1.5">
          <Label htmlFor="identifier" className="text-sm font-semibold text-gray-700">
            {t("identifier_label")}
          </Label>
          <div className="flex">
            {isPhone && (
              <select
                value={phoneRegion}
                onChange={(e) => setPhoneRegion(e.target.value)}
                className="inline-flex items-center rounded-l-lg border border-r-0 border-gray-200 bg-gray-50 px-2 text-sm text-gray-600 focus:outline-none"
              >
                {PHONE_REGIONS.map((r) => (
                  <option key={r.code} value={r.code}>
                    {r.flag} {r.dialCode}
                  </option>
                ))}
              </select>
            )}
            <input
              id="identifier"
              type="text"
              value={identifier}
              onChange={(e) => {
                const v = e.target.value;
                setIdentifier(v);
                if (looksLikePhone(v)) setPhoneRegion(guessPhoneRegion(v));
                if (idErr) setIdErr(null);
              }}
              onBlur={() => setIdErr(identifier ? null : t("identifier_required"))}
              placeholder={t("identifier_placeholder")}
              autoComplete="username"
              className={
                "w-full h-12 px-4 border bg-white text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 transition-all " +
                (isPhone ? "rounded-r-lg rounded-l-none " : "rounded-lg ") +
                (idErr
                  ? "border-red-400 focus:border-red-500 focus:ring-red-500/15"
                  : "border-gray-200 focus:border-[#FF6B35] focus:ring-[#FF6B35]/15")
              }
            />
          </div>
          {idErr && <p className="text-xs text-red-500">{idErr}</p>}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="password" className="text-sm font-semibold text-gray-700">
            {t("password_label")}
          </Label>
          <div className="relative">
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => { setPassword(e.target.value); if (pwdErr) setPwdErr(null); }}
              onBlur={() => setPwdErr(password ? null : t("password_required"))}
              placeholder={t("password_placeholder")}
              autoComplete="current-password"
              className={
                "w-full h-12 px-4 pr-12 rounded-lg border bg-white text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 transition-all " +
                (pwdErr
                  ? "border-red-400 focus:border-red-500 focus:ring-red-500/15"
                  : "border-gray-200 focus:border-[#FF6B35] focus:ring-[#FF6B35]/15")
              }
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
              tabIndex={-1}
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          {pwdErr && <p className="text-xs text-red-500">{pwdErr}</p>}
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="mt-2 flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-[#0D4D4D] text-base font-semibold text-white shadow-sm transition-all hover:bg-[#0a3d3d] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-70"
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

      <div className="mt-3 text-right">
        <Link href="/forgot-password" className="text-sm text-gray-500 transition-colors hover:text-[#0D4D4D]">
          {t("forgotPassword")}
        </Link>
      </div>

      <div className="mt-4 text-center">
        <p className="text-sm text-gray-500">
          {t("no_account")}{" "}
          <Link href="/register" className="font-semibold text-[#FF6B35] transition-colors hover:text-[#e05a25]">
            {t("register_now")}
          </Link>
        </p>
      </div>

      <div className="mt-4 flex items-center justify-center gap-3">
        <Link href="/" className="text-xs text-gray-400 transition-colors hover:text-gray-600">
          {tc("back_to_home")}
        </Link>
        <span className="text-xs text-gray-300">|</span>
        <LocaleSwitcher variant="full" />
      </div>
    </>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-[#0D4D4D]" />
        </div>
      }
    >
      <LoginContent />
    </Suspense>
  );
}
