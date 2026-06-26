"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { AlertCircle, CheckCircle2, Eye, EyeOff, Loader2, MessageCircle } from "lucide-react";

import { Label } from "@/components/ui/label";
import { Link } from "@/i18n/navigation";
import { LocaleSwitcher } from "@/components/i18n/LocaleSwitcher";
import { validateEmail, validatePassword } from "@/lib/validators";
import { useWhatsApp } from "@/hooks/useWhatsApp";
import { getApiBase } from "@/lib/env";

type Step = "email" | "code" | "done";

export default function ForgotPasswordPage() {
  const t = useTranslations("auth.forgotPassword");
  const tc = useTranslations("common");
  const wa = useWhatsApp();

  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [emailErr, setEmailErr] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [codeErr, setCodeErr] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [pwdErr, setPwdErr] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Step 1: 发送验证码
  const handleSendCode = async (e: React.FormEvent) => {
    e.preventDefault();
    const err = validateEmail(email, {
      required: tc("err_email_required"),
      format: tc("err_email_format"),
      domain: tc("err_email_domain"),
    });
    if (err) { setEmailErr(err); return; }
    setEmailErr(null);
    setError(null);
    setSubmitting(true);

    try {
      const fd = new FormData();
      fd.append("email", email);
      const res = await fetch(`${getApiBase()}/api/v1/auth/forgot-password`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) {
        const json = await res.json().catch(() => null);
        // 邮箱不存在的错误显示在邮箱字段下方
        const errMsg = json?.errors?.[0]?.message || json?.message || t("error_generic");
        if (json?.errors?.[0]?.field === "email") {
          setEmailErr(errMsg);
        } else {
          setError(errMsg);
        }
      } else {
        setStep("code");
      }
    } catch {
      setError(t("error_network"));
    } finally {
      setSubmitting(false);
    }
  };

  // Step 2: 验证码 + 新密码
  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    let hasErr = false;
    if (!code.trim() || code.trim().length !== 6) {
      setCodeErr(t("code_invalid"));
      hasErr = true;
    } else {
      setCodeErr(null);
    }
    const pe = validatePassword(password);
    if (pe) { setPwdErr(pe); hasErr = true; } else { setPwdErr(null); }
    if (hasErr) return;

    setError(null);
    setSubmitting(true);

    try {
      const fd = new FormData();
      fd.append("email", email);
      fd.append("code", code.trim());
      fd.append("new_password", password);
      const res = await fetch(`${getApiBase()}/api/v1/auth/reset-password`, {
        method: "POST",
        body: fd,
      });
      const json = await res.json().catch(() => null);
      if (!res.ok) {
        const msg = json?.message || json?.errors?.[0]?.message || t("error_generic");
        setError(msg);
      } else {
        setStep("done");
      }
    } catch {
      setError(t("error_network"));
    } finally {
      setSubmitting(false);
    }
  };

  // WhatsApp 预填文案
  const waLink = (() => {
    const base = wa.link;
    if (!base) return null;
    const text = email
      ? `Hi, I need help resetting my password. My registered email is: ${email}`
      : "Hi, I need help resetting my password.";
    const sep = base.includes("?") ? "&" : "?";
    return `${base}${sep}text=${encodeURIComponent(text)}`;
  })();

  // Step 3: 完成
  if (step === "done") {
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
        <p className="mt-2 text-sm text-gray-500">
          {step === "email" ? t("subtitle") : t("code_subtitle")}
        </p>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2.5 rounded-lg border-l-4 border-red-500 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {step === "email" && (
        <>
          <form onSubmit={handleSendCode} className="space-y-4">
            <div className="space-y-1.5">
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => { setEmail(e.target.value); if (emailErr) setEmailErr(null); }}
                onBlur={() => {
                  if (email) setEmailErr(validateEmail(email, {
                    required: tc("err_email_required"),
                    format: tc("err_email_format"),
                    domain: tc("err_email_domain"),
                  }));
                }}
                placeholder="your@email.com"
                autoComplete="email"
                className={
                  "h-11 w-full rounded-lg border bg-white px-3 text-sm text-gray-800 placeholder-gray-400 transition-all focus:outline-none focus:ring-2 " +
                  (emailErr
                    ? "border-red-400 focus:border-red-500 focus:ring-red-500/15"
                    : "border-gray-200 focus:border-[#0D4D4D] focus:ring-[#0D4D4D]/15")
                }
              />
              {emailErr && <p className="text-xs text-red-500">{emailErr}</p>}
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#0D4D4D] text-sm font-semibold text-white shadow-sm transition-all hover:bg-[#0a3d3d] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-70"
            >
              {submitting ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> {t("submitting")}</>
              ) : (
                t("send_code")
              )}
            </button>
          </form>

          {/* 分割线 */}
          <div className="my-5 flex items-center gap-3">
            <div className="h-px flex-1 bg-gray-200" />
            <span className="text-xs text-gray-400">{t("or")}</span>
            <div className="h-px flex-1 bg-gray-200" />
          </div>

          {/* 联系客服 */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
              <MessageCircle className="h-4 w-4" />
              {t("method_whatsapp")}
            </div>
            <a
              href={waLink || "#"}
              target="_blank"
              rel="noopener noreferrer"
              className="flex h-11 w-full items-center justify-center gap-2 rounded-lg border-2 border-[#25D366] bg-[#25D366]/5 text-sm font-semibold text-[#25D366] transition-all hover:bg-[#25D366]/10"
            >
              <MessageCircle className="h-4 w-4" />
              {t("contact_whatsapp")}
            </a>
          </div>
        </>
      )}

      {step === "code" && (
        <form onSubmit={handleResetPassword} className="space-y-4">
          {/* 验证码已发送提示 */}
          <div className="flex items-start gap-3 rounded-lg border-l-4 border-[#10B981] bg-[#10B981]/10 px-4 py-3 text-sm text-[#047857]">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{t("code_sent", { email })}</span>
          </div>

          {/* 验证码 */}
          <div className="space-y-1.5">
            <Label htmlFor="code" className="text-sm font-semibold text-gray-700">
              {t("code_label")}
            </Label>
            <input
              id="code"
              type="text"
              value={code}
              onChange={(e) => {
                const v = e.target.value.replace(/\D/g, "").slice(0, 6);
                setCode(v);
                if (codeErr) setCodeErr(null);
              }}
              placeholder="000000"
              inputMode="numeric"
              maxLength={6}
              autoComplete="one-time-code"
              className={
                "h-12 w-full rounded-lg border bg-white px-3 text-center text-lg font-bold tracking-[0.5em] text-gray-800 placeholder-gray-300 transition-all focus:outline-none focus:ring-2 " +
                (codeErr
                  ? "border-red-400 focus:border-red-500 focus:ring-red-500/15"
                  : "border-gray-200 focus:border-[#0D4D4D] focus:ring-[#0D4D4D]/15")
              }
            />
            {codeErr && <p className="text-xs text-red-500">{codeErr}</p>}
          </div>

          {/* 新密码 */}
          <div className="space-y-1.5">
            <Label htmlFor="password" className="text-sm font-semibold text-gray-700">
              {t("new_password")}
            </Label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => { setPassword(e.target.value); if (pwdErr) setPwdErr(null); }}
                onBlur={() => { if (password) setPwdErr(validatePassword(password)); }}
                autoComplete="new-password"
                className={
                  "h-11 w-full rounded-lg border bg-white px-3 pr-12 text-sm text-gray-800 transition-all focus:outline-none focus:ring-2 " +
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
              <><Loader2 className="h-4 w-4 animate-spin" /> {t("resetting")}</>
            ) : (
              t("reset_submit")
            )}
          </button>

          {/* 重新发送 */}
          <div className="text-center text-sm text-gray-500">
            <span>{t("not_received")} </span>
            <button
              type="button"
              onClick={() => { setStep("email"); setError(null); setCode(""); }}
              className="font-semibold text-[#FF6B35] hover:text-[#e05a25]"
            >
              {t("resend")}
            </button>
          </div>
        </form>
      )}

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
