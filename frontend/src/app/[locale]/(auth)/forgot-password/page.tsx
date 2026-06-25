"use client";

import React, { useEffect, useRef, useState } from "react";
import { useRouter } from "@/i18n/navigation";
import { useTranslations } from "next-intl";
import {
  AlertCircle,
  Check,
  CheckCircle2,
  Eye,
  EyeOff,
  Loader2,
} from "lucide-react";

import { Label } from "@/components/ui/label";
import { authApi } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import {
  validateEmail,
  validatePassword,
  PASSWORD_MIN_LENGTH,
  PASSWORD_MAX_LENGTH,
} from "@/lib/validators";
import { Link } from "@/i18n/navigation";
import { LocaleSwitcher } from "@/components/i18n/LocaleSwitcher";

const INPUT_BASE =
  "h-11 w-full rounded-lg border bg-white px-3 text-sm text-gray-800 placeholder-gray-400 transition-all focus:outline-none focus:ring-2";
const INPUT_OK =
  "border-gray-200 focus:border-[#0D4D4D] focus:ring-[#0D4D4D]/15";
const INPUT_ERR =
  "border-red-400 focus:border-red-500 focus:ring-red-500/15";

function inputCls(error: string | null, extra = ""): string {
  return `${INPUT_BASE} ${error ? INPUT_ERR : INPUT_OK} ${extra}`;
}

export default function ForgotPasswordPage() {
  const router = useRouter();
  const t = useTranslations("forgotPassword");
  const tc = useTranslations("common");

  const [email, setEmail] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [verificationToken, setVerificationToken] = useState("");
  const [emailVerified, setEmailVerified] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const [codeSending, setCodeSending] = useState(false);
  const [codeVerifying, setCodeVerifying] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [codeCooldown, setCooldown] = useState(0);
  const cooldownRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [errors, setErrors] = useState<Record<string, string | null>>({});
  const [submitError, setSubmitError] = useState("");
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    return () => {
      if (cooldownRef.current) clearInterval(cooldownRef.current);
    };
  }, []);

  const pwdHasDigit = /\d/.test(newPassword);
  const pwdHasUpper = /[A-Z]/.test(newPassword);
  const pwdHasLower = /[a-z]/.test(newPassword);
  const pwdHasSpecial = /[^A-Za-z0-9]/.test(newPassword);
  const pwdLenOk = newPassword.length >= PASSWORD_MIN_LENGTH && newPassword.length <= PASSWORD_MAX_LENGTH;

  const handleSendCode = async () => {
    const emailErr = validateEmail(email);
    if (!email) {
      setErrors((e) => ({ ...e, email: t("err_email_required") }));
      return;
    }
    if (emailErr) {
      setErrors((e) => ({ ...e, email: emailErr }));
      return;
    }
    setCodeSending(true);
    setSubmitError("");
    try {
      await authApi.sendVerificationCode(email, "RESET_PASSWORD");
      setCooldown(60);
      cooldownRef.current = setInterval(() => {
        setCooldown((prev) => {
          if (prev <= 1) {
            clearInterval(cooldownRef.current!);
            cooldownRef.current = null;
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
      setErrors((e) => ({ ...e, email: null }));
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors((e) => ({ ...e, email: err.message }));
      }
    } finally {
      setCodeSending(false);
    }
  };

  const handleVerifyCode = async () => {
    if (verificationCode.length !== 6) return;
    setCodeVerifying(true);
    try {
      const result = await authApi.verifyCode(email, verificationCode, "RESET_PASSWORD");
      setVerificationToken(result.verification_token);
      setEmailVerified(true);
      setErrors((e) => ({ ...e, verificationCode: null }));
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors((e) => ({ ...e, verificationCode: err.message }));
      }
    } finally {
      setCodeVerifying(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError("");

    if (!emailVerified) {
      setSubmitError(t("err_email_required"));
      return;
    }

    const pwdErr = validatePassword(newPassword);
    if (pwdErr) {
      setErrors((er) => ({ ...er, newPassword: pwdErr }));
      return;
    }
    if (newPassword !== confirmPassword) {
      setErrors((er) => ({ ...er, confirmPassword: t("err_password_mismatch") }));
      return;
    }

    setSubmitting(true);
    try {
      await authApi.resetPassword(verificationToken, newPassword, confirmPassword);
      setSuccess(true);
      setTimeout(() => router.replace("/login"), 2000);
    } catch (err) {
      if (err instanceof ApiError) {
        setSubmitError(err.message);
      } else {
        setSubmitError("An error occurred");
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (success) {
    return (
      <div className="flex flex-col items-center gap-4 py-8">
        <CheckCircle2 className="h-12 w-12 text-green-500" />
        <p className="text-center text-sm text-gray-600">{t("reset_success")}</p>
      </div>
    );
  }

  return (
    <>
      <div className="mb-6 text-center">
        <h2 className="text-xl font-bold text-gray-900">{t("pageTitle")}</h2>
        <p className="mt-1 text-sm text-gray-400">{t("subtitle")}</p>
      </div>

      {submitError && (
        <div className="mb-5 flex items-center gap-2.5 rounded-lg border-l-4 border-red-500 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{submitError}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        {/* Email + Send Code */}
        <div className="space-y-1.5">
          <Label htmlFor="email" className="text-sm font-semibold text-gray-700">
            {t("label_email")} <span className="text-red-500">*</span>
          </Label>
          <div className="flex gap-2">
            <input
              id="email" type="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (emailVerified) {
                  setEmailVerified(false);
                  setVerificationToken("");
                  setVerificationCode("");
                }
                if (errors.email) setErrors((er) => ({ ...er, email: null }));
              }}
              placeholder={t("ph_email")}
              readOnly={emailVerified}
              className={inputCls(errors.email || null, emailVerified ? "bg-gray-50" : "")}
            />
            {!emailVerified && (
              <button
                type="button"
                onClick={handleSendCode}
                disabled={codeSending || codeCooldown > 0 || !email}
                className="shrink-0 rounded-lg bg-[#0D4D4D] px-4 text-sm font-medium text-white transition-colors hover:bg-[#0a3d3d] disabled:bg-gray-300 disabled:cursor-not-allowed"
              >
                {codeSending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : codeCooldown > 0 ? (
                  `${codeCooldown}s`
                ) : (
                  t("btn_send_code")
                )}
              </button>
            )}
            {emailVerified && (
              <span className="flex shrink-0 items-center gap-1 text-sm text-green-600">
                <CheckCircle2 className="h-4 w-4" /> {t("email_verified")}
              </span>
            )}
          </div>
          {errors.email && <p className="text-xs text-red-500">{errors.email}</p>}
        </div>

        {/* Verification Code */}
        {!emailVerified && email && (
          <div className="space-y-1.5">
            <Label htmlFor="code" className="text-sm font-semibold text-gray-700">
              {t("label_code")} <span className="text-red-500">*</span>
            </Label>
            <div className="flex gap-2">
              <input
                id="code" type="text" inputMode="numeric"
                value={verificationCode}
                onChange={(e) => {
                  const v = e.target.value.replace(/\D/g, "").slice(0, 6);
                  setVerificationCode(v);
                  if (errors.verificationCode) setErrors((er) => ({ ...er, verificationCode: null }));
                }}
                placeholder={t("ph_code")}
                maxLength={6}
                className={inputCls(errors.verificationCode || null)}
              />
              <button
                type="button"
                onClick={handleVerifyCode}
                disabled={codeVerifying || verificationCode.length !== 6}
                className="shrink-0 rounded-lg bg-[#0D4D4D] px-4 text-sm font-medium text-white transition-colors hover:bg-[#0a3d3d] disabled:bg-gray-300 disabled:cursor-not-allowed"
              >
                {codeVerifying ? <Loader2 className="h-4 w-4 animate-spin" /> : t("btn_verify")}
              </button>
            </div>
            {errors.verificationCode && (
              <p className="text-xs text-red-500">{errors.verificationCode}</p>
            )}
          </div>
        )}

        {/* New Password */}
        <div className="space-y-1.5">
          <Label htmlFor="newPassword" className="text-sm font-semibold text-gray-700">
            {t("label_new_password")} <span className="text-red-500">*</span>
          </Label>
          <div className="relative">
            <input
              id="newPassword"
              type={showPassword ? "text" : "password"}
              value={newPassword}
              onChange={(e) => {
                setNewPassword(e.target.value);
                if (errors.newPassword) setErrors((er) => ({ ...er, newPassword: null }));
              }}
              placeholder={t("ph_new_password")}
              autoComplete="new-password"
              className={inputCls(errors.newPassword || null, "pr-12")}
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 transition-colors hover:text-gray-600"
              tabIndex={-1}
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          {errors.newPassword && <p className="text-xs text-red-500">{errors.newPassword}</p>}
          <div className="mt-1 flex flex-wrap items-center gap-x-2 text-[11px]">
            <span className={pwdLenOk ? "text-green-600" : "text-gray-400"}>
              {pwdLenOk && <Check className="mr-0.5 inline h-3 w-3" />}11-50
            </span>
            <span className="text-gray-300">|</span>
            <span className={pwdHasDigit ? "text-green-600" : "text-gray-400"}>
              {pwdHasDigit && <Check className="mr-0.5 inline h-3 w-3" />}0-9
            </span>
            <span className={pwdHasUpper ? "text-green-600" : "text-gray-400"}>
              {pwdHasUpper && <Check className="mr-0.5 inline h-3 w-3" />}A-Z
            </span>
            <span className={pwdHasLower ? "text-green-600" : "text-gray-400"}>
              {pwdHasLower && <Check className="mr-0.5 inline h-3 w-3" />}a-z
            </span>
            <span className={pwdHasSpecial ? "text-green-600" : "text-gray-400"}>
              {pwdHasSpecial && <Check className="mr-0.5 inline h-3 w-3" />}!@#
            </span>
          </div>
        </div>

        {/* Confirm Password */}
        <div className="space-y-1.5">
          <Label htmlFor="confirmPassword" className="text-sm font-semibold text-gray-700">
            {t("label_confirm_password")} <span className="text-red-500">*</span>
          </Label>
          <div className="relative">
            <input
              id="confirmPassword"
              type={showConfirm ? "text" : "password"}
              value={confirmPassword}
              onChange={(e) => {
                setConfirmPassword(e.target.value);
                if (errors.confirmPassword) setErrors((er) => ({ ...er, confirmPassword: null }));
              }}
              placeholder={t("ph_confirm_password")}
              autoComplete="new-password"
              className={inputCls(errors.confirmPassword || null, "pr-12")}
            />
            <button
              type="button"
              onClick={() => setShowConfirm(!showConfirm)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 transition-colors hover:text-gray-600"
              tabIndex={-1}
            >
              {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          {errors.confirmPassword ? (
            <p className="text-xs text-red-500">{errors.confirmPassword}</p>
          ) : (
            confirmPassword && newPassword && newPassword === confirmPassword && (
              <p className="flex items-center gap-1 text-xs text-green-600">
                <CheckCircle2 className="h-3 w-3" /> Match
              </p>
            )
          )}
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={submitting || !emailVerified}
          className="mt-2 flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-[#0D4D4D] text-base font-semibold text-white shadow-sm transition-all hover:bg-[#0a3d3d] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-70"
        >
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              {t("btn_reset")}
            </>
          ) : (
            t("btn_reset")
          )}
        </button>
      </form>

      <div className="mt-5 text-center">
        <Link href="/login" className="text-sm text-gray-500 transition-colors hover:text-[#0D4D4D]">
          ← {t("back_to_login")}
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
