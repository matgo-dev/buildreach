"use client";
// /register 入口:角色选择后:
// - BUYER → 原单页表单(不动)
// - SUPPLIER → 3 步向导(Step 1 国家 / Step 2 语言 / Step 3 表单)

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  Building2,
  CheckCircle2,
  ChevronRight,
  Eye,
  EyeOff,
  Loader2,
  ShoppingCart,
} from "lucide-react";

import { Label } from "@/components/ui/label";
import { authApi } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import {
  validateEmail,
  validatePassword,
  validatePasswordConfirm,
  validatePhoneOptional,
  validateRequired,
  validateUsc,
  validateUsernameOptional,
} from "@/lib/validators";
import type { CountryCode, LanguageCode } from "@/config/country-registration-rules";

import { StepIndicator } from "./_components/StepIndicator";
import { StepCountry } from "./_components/StepCountry";
import { StepLanguage } from "./_components/StepLanguage";
import { StepForm } from "./_components/StepForm";
import { useRegisterDraft } from "./_components/useRegisterDraft";
import { useBeforeUnload } from "./_components/useBeforeUnload";
import { useAuthStore } from "@/stores/authStore";
import { defaultDashboardOf } from "@/config/navigation";

type Role = "BUYER" | "SUPPLIER" | "";

type BuyerFieldName =
  | "name"
  | "email"
  | "username"
  | "phone"
  | "password"
  | "confirmPassword"
  | "companyName"
  | "unifiedSocialCreditCode";

interface BuyerFormState {
  name: string;
  email: string;
  username: string;
  phone: string;
  password: string;
  confirmPassword: string;
  companyName: string;
  unifiedSocialCreditCode: string;
}

const initialBuyerForm: BuyerFormState = {
  name: "",
  email: "",
  username: "",
  phone: "",
  password: "",
  confirmPassword: "",
  companyName: "",
  unifiedSocialCreditCode: "",
};

const INPUT_BASE =
  "h-11 w-full rounded-lg border bg-white px-3 text-sm text-gray-800 placeholder-gray-400 transition-all focus:outline-none focus:ring-2";
const INPUT_OK_BUYER =
  "border-gray-200 focus:border-[#003366] focus:ring-[#003366]/15";
const INPUT_ERR =
  "border-red-400 focus:border-red-500 focus:ring-red-500/15";

function buyerInputCls(error: string | null, extra = ""): string {
  return `${INPUT_BASE} ${error ? INPUT_ERR : INPUT_OK_BUYER} ${extra}`;
}

export default function RegisterPage() {
  const router = useRouter();
  const [role, setRole] = useState<Role>("");

  // SUPPLIER 草稿(sessionStorage)
  const { draft, hydrated, update, clearDraft, clearRegistrationNo, clearLanguagePreference } =
    useRegisterDraft();

  // PRD v1.4 Δ8:已登录用户访问 /register 自动跳工作台
  const me = useAuthStore((s) => s.user);
  const authLoaded = useAuthStore((s) => s.loaded);
  useEffect(() => {
    if (authLoaded && me?.roles?.length) {
      router.replace(defaultDashboardOf(me.roles));
    }
  }, [authLoaded, me, router]);

  // 切换角色时清掉 SUPPLIER 草稿(PRD §2.3:跨角色切换清掉草稿)
  const handleSwitchRole = (next: Role) => {
    if (role === "SUPPLIER" && next !== "SUPPLIER") clearDraft();
    setRole(next);
  };

  // SUPPLIER hydrate 完后,如果 draft.currentStep > 1,自动锁角色为 SUPPLIER
  useEffect(() => {
    if (hydrated && draft.country_code && !role) {
      setRole("SUPPLIER");
    }
  }, [hydrated, draft.country_code, role]);

  // PRD v1.4 Δ7:有未提交数据时关 tab / 刷新 弹原生确认框
  const hasAnyNonEmptyDraftField =
    !!draft.country_code ||
    !!draft.language_preference ||
    !!draft.company_name ||
    !!draft.registration_no ||
    !!draft.name ||
    !!draft.phone ||
    !!draft.email;
  const shouldWarnOnUnload =
    role === "SUPPLIER" && draft.currentStep >= 2 && hasAnyNonEmptyDraftField;
  useBeforeUnload(shouldWarnOnUnload);

  return (
    <>
      <div className="mb-6 text-center">
        <h2 className="text-xl font-bold text-gray-900">创建账户</h2>
        {!role && (
          <p className="mt-1 text-sm text-gray-400">选择您的角色开始注册</p>
        )}
      </div>

      {/* 角色选择 */}
      {!role && (
        <div className="mb-6">
          <p className="mb-4 text-center text-sm text-gray-500">请选择您的角色</p>
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => handleSwitchRole("BUYER")}
              className="group flex flex-col items-center gap-3 rounded-xl border-2 border-gray-200 p-5 transition-all hover:border-[#003366] hover:bg-[#003366]/5"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50 transition-colors group-hover:bg-[#003366]/10">
                <ShoppingCart className="h-6 w-6 text-gray-400 transition-colors group-hover:text-[#003366]" />
              </div>
              <div className="text-center">
                <p className="text-sm font-semibold text-gray-700 transition-colors group-hover:text-[#003366]">
                  我是采购方
                </p>
                <p className="mt-0.5 text-xs text-gray-400">央企项目部</p>
              </div>
              <ChevronRight className="h-4 w-4 text-gray-300 transition-colors group-hover:text-[#003366]" />
            </button>
            <button
              type="button"
              onClick={() => handleSwitchRole("SUPPLIER")}
              className="group flex flex-col items-center gap-3 rounded-xl border-2 border-gray-200 p-5 transition-all hover:border-[#FF6B35] hover:bg-[#FF6B35]/5"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-orange-50 transition-colors group-hover:bg-[#FF6B35]/10">
                <Building2 className="h-6 w-6 text-gray-400 transition-colors group-hover:text-[#FF6B35]" />
              </div>
              <div className="text-center">
                <p className="text-sm font-semibold text-gray-700 transition-colors group-hover:text-[#FF6B35]">
                  我是供应商
                </p>
                <p className="mt-0.5 text-xs text-gray-400">海外材料供货方</p>
              </div>
              <ChevronRight className="h-4 w-4 text-gray-300 transition-colors group-hover:text-[#FF6B35]" />
            </button>
          </div>
        </div>
      )}

      {role && (
        <>
          {/* 已选角色徽标 */}
          <div
            className={
              "mb-5 flex items-center gap-3 rounded-xl p-3 " +
              (role === "BUYER" ? "bg-[#003366]/10" : "bg-[#FF6B35]/10")
            }
          >
            <div
              className={
                "flex h-8 w-8 items-center justify-center rounded-lg " +
                (role === "BUYER" ? "bg-[#003366]/20" : "bg-[#FF6B35]/20")
              }
            >
              {role === "BUYER" ? (
                <ShoppingCart className="h-4 w-4 text-[#003366]" />
              ) : (
                <Building2 className="h-4 w-4 text-[#FF6B35]" />
              )}
            </div>
            <span
              className={
                "text-sm font-semibold " +
                (role === "BUYER" ? "text-[#003366]" : "text-[#FF6B35]")
              }
            >
              {role === "BUYER" ? "采购方注册" : "供应商入驻"}
            </span>
            <button
              type="button"
              onClick={() => handleSwitchRole("")}
              className="ml-auto text-xs text-gray-400 underline hover:text-gray-600"
            >
              更改角色
            </button>
          </div>

          {role === "BUYER" && <BuyerForm onSubmitted={(prefill) => {
            try { sessionStorage.setItem("prefill_login", JSON.stringify(prefill)); } catch { /* ignore */ }
            router.replace("/login?registered=1");
          }} />}

          {role === "SUPPLIER" && (
            <SupplierWizard
              draft={draft}
              hydrated={hydrated}
              update={update}
              clearRegistrationNo={clearRegistrationNo}
              clearLanguagePreference={clearLanguagePreference}
              onSubmitted={() => {
                clearDraft();
                router.replace("/login?registered=1");
              }}
            />
          )}
        </>
      )}

      <div className="mt-5 text-center">
        <p className="text-sm text-gray-500">
          已有账户?{" "}
          <Link href="/login" className="font-semibold text-[#FF6B35] transition-colors hover:text-[#e05a25]">
            立即登录
          </Link>
        </p>
      </div>

      <div className="mt-3 text-center">
        <Link href="/" className="text-xs text-gray-400 transition-colors hover:text-gray-600">
          返回首页
        </Link>
      </div>
    </>
  );
}

// ===== SUPPLIER 3 步向导(纯前端编排,仅 Step 3 提交时调一次后端) =====

interface SupplierWizardProps {
  draft: ReturnType<typeof useRegisterDraft>["draft"];
  hydrated: boolean;
  update: ReturnType<typeof useRegisterDraft>["update"];
  clearRegistrationNo: ReturnType<typeof useRegisterDraft>["clearRegistrationNo"];
  clearLanguagePreference: ReturnType<typeof useRegisterDraft>["clearLanguagePreference"];
  onSubmitted: () => void;
}

function SupplierWizard({
  draft,
  hydrated,
  update,
  clearRegistrationNo,
  clearLanguagePreference,
  onSubmitted,
}: SupplierWizardProps) {
  if (!hydrated) {
    return (
      <div className="flex items-center justify-center py-10">
        <Loader2 className="h-6 w-6 animate-spin text-[#003366]" />
      </div>
    );
  }

  const step = draft.currentStep;

  // 已完成判定:Step 1 始终可达;Step 2 需要选过国家;Step 3 需要语言也选过
  const reachable: (1 | 2 | 3)[] = [1];
  if (draft.country_code) reachable.push(2);
  if (draft.country_code && draft.language_preference) reachable.push(3);

  // 步骤条点击跳转(只允许跳到 reachable 里的 step)
  const jumpToStep = (target: 1 | 2 | 3) => {
    if (!reachable.includes(target)) return;
    update({ currentStep: target });
  };

  return (
    <>
      <StepIndicator current={step} reachable={reachable} onStepClick={jumpToStep} />
      {step === 1 && (
        <StepCountry
          selected={draft.country_code}
          onSelect={(code: CountryCode) => {
            // PRD v1.4 Δ4:改国家时自动清 registration_no + 重置 language_preference
            // 其他字段(company_name / name / phone / email)保留
            if (code !== draft.country_code) {
              clearRegistrationNo();
              clearLanguagePreference();
            }
            update({ country_code: code });
          }}
          onNext={() => update({ currentStep: 2 })}
        />
      )}
      {step === 2 && draft.country_code && (
        <StepLanguage
          countryCode={draft.country_code}
          selected={draft.language_preference}
          onSelect={(lang: LanguageCode) => update({ language_preference: lang })}
          onBack={() => update({ currentStep: 1 })}
          onNext={() => update({ currentStep: 3 })}
        />
      )}
      {step === 3 && draft.country_code && draft.language_preference && (
        <StepForm
          countryCode={draft.country_code}
          languagePreference={draft.language_preference}
          draft={{
            company_name: draft.company_name,
            registration_no: draft.registration_no,
            name: draft.name,
            phone: draft.phone,
            email: draft.email,
          }}
          updateDraft={(p) => update(p)}
          onBack={() => update({ currentStep: 2 })}
          onSubmitted={onSubmitted}
        />
      )}
    </>
  );
}

// ===== BUYER 单页表单(原逻辑保留,SUPPLIER 分支已下沉到 3 步向导) =====

interface BuyerFormProps {
  onSubmitted: (prefill: { identifier: string; password: string }) => void;
}

function BuyerForm({ onSubmitted }: BuyerFormProps) {
  const [form, setForm] = useState<BuyerFormState>(initialBuyerForm);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Partial<Record<BuyerFieldName, string | null>>>({});
  const [touched, setTouched] = useState<Partial<Record<BuyerFieldName, boolean>>>({});

  const validateField = (field: BuyerFieldName, value: string, pwd?: string): string | null => {
    switch (field) {
      case "name":
        return validateRequired(value, "姓名");
      case "email":
        return validateEmail(value);
      case "username":
        return validateUsernameOptional(value);
      case "phone":
        return validatePhoneOptional(value);
      case "password":
        return validatePassword(value);
      case "confirmPassword":
        return validatePasswordConfirm(pwd ?? form.password, value);
      case "companyName":
        return validateRequired(value, "公司名称");
      case "unifiedSocialCreditCode":
        return validateUsc(value);
    }
  };

  const setField = (field: BuyerFieldName, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) setErrors((e) => ({ ...e, [field]: null }));
    if (field === "password" && errors.confirmPassword) {
      setErrors((e) => ({ ...e, confirmPassword: null }));
    }
  };

  const handleBlur = (field: BuyerFieldName) => {
    setTouched((t) => ({ ...t, [field]: true }));
    setErrors((e) => ({ ...e, [field]: validateField(field, form[field]) }));
  };

  const errOf = (field: BuyerFieldName): string | null =>
    touched[field] ? errors[field] ?? null : null;

  const validateAll = (): string => {
    const fields: BuyerFieldName[] = [
      "name", "email", "username", "phone", "password", "confirmPassword",
      "companyName", "unifiedSocialCreditCode",
    ];
    const newErrors: Partial<Record<BuyerFieldName, string | null>> = {};
    const newTouched: Partial<Record<BuyerFieldName, boolean>> = {};
    let firstError = "";
    for (const f of fields) {
      const err = validateField(f, form[f]);
      newTouched[f] = true;
      newErrors[f] = err;
      if (err && !firstError) firstError = err;
    }
    setTouched((t) => ({ ...t, ...newTouched }));
    setErrors((e) => ({ ...e, ...newErrors }));
    return firstError;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const v = validateAll();
    if (v) {
      setSubmitError(v);
      return;
    }
    setSubmitError("");
    setLoading(true);
    try {
      await authApi.registerBuyer({
        email: form.email,
        username: form.username || undefined,
        name: form.name,
        phone: form.phone || undefined,
        password: form.password,
        company_name: form.companyName,
        unified_social_credit_code: form.unifiedSocialCreditCode,
      });
      onSubmitted({
        identifier: form.username || form.phone || form.email,
        password: form.password,
      });
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "注册失败,请稍后重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {submitError && (
        <div className="mb-5 flex items-center gap-2.5 rounded-lg border-l-4 border-red-500 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{submitError}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <BuyerField
          id="companyName" label="公司名称" required
          value={form.companyName}
          onChange={(v) => setField("companyName", v)}
          onBlur={() => handleBlur("companyName")}
          error={errOf("companyName")}
          placeholder="请填写完整公司名称"
        />
        <BuyerField
          id="unifiedSocialCreditCode" label="统一社会信用代码" required
          hint="(18 位大写字母与数字)"
          value={form.unifiedSocialCreditCode}
          onChange={(v) => setField("unifiedSocialCreditCode", v.toUpperCase().slice(0, 18))}
          onBlur={() => handleBlur("unifiedSocialCreditCode")}
          error={errOf("unifiedSocialCreditCode")}
          placeholder="如 91110000XXXXXXXXX1"
          maxLength={18}
          extraInputClass="uppercase"
          footnote="系统按信用代码识别企业:首次填写将创建新组织,与已有组织信用代码相同则自动加入。"
        />

        <div className="grid grid-cols-2 gap-3">
          <BuyerField
            id="name" label="姓名" required
            value={form.name}
            onChange={(v) => setField("name", v)}
            onBlur={() => handleBlur("name")}
            error={errOf("name")}
            placeholder="您的姓名"
          />
          <BuyerField
            id="phone" label="手机号"
            hint="(选填,可作登录凭证)"
            value={form.phone}
            onChange={(v) => setField("phone", v.replace(/\D/g, "").slice(0, 11))}
            onBlur={() => handleBlur("phone")}
            error={errOf("phone")}
            placeholder="11 位"
            inputMode="numeric"
          />
        </div>

        <BuyerField
          id="email" label="邮箱地址" required type="email"
          value={form.email}
          onChange={(v) => setField("email", v)}
          onBlur={() => handleBlur("email")}
          error={errOf("email")}
          placeholder="your@email.com"
          autoComplete="email"
        />

        <BuyerField
          id="username" label="用户名"
          hint="(选填,3-50 位字母/数字/下划线/短横;用于代替邮箱登录)"
          value={form.username}
          onChange={(v) => setField("username", v)}
          onBlur={() => handleBlur("username")}
          error={errOf("username")}
          placeholder="如 zhang_san"
          autoComplete="username"
        />

        <div className="space-y-1.5">
          <Label htmlFor="password" className="text-sm font-semibold text-gray-700">
            密码 * <span className="font-normal text-gray-400">(11-50 位,需 3 类字符)</span>
          </Label>
          <div className="relative">
            <input
              id="password" name="password"
              type={showPassword ? "text" : "password"}
              value={form.password}
              onChange={(e) => setField("password", e.target.value)}
              onBlur={() => handleBlur("password")}
              placeholder="请输入密码"
              autoComplete="new-password"
              className={buyerInputCls(errOf("password"), "pr-12")}
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
          {errOf("password") && <p className="text-xs text-red-500">{errOf("password")}</p>}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="confirmPassword" className="text-sm font-semibold text-gray-700">
            确认密码 *
          </Label>
          <div className="relative">
            <input
              id="confirmPassword" name="confirmPassword"
              type={showConfirm ? "text" : "password"}
              value={form.confirmPassword}
              onChange={(e) => setField("confirmPassword", e.target.value)}
              onBlur={() => handleBlur("confirmPassword")}
              placeholder="再次输入密码"
              autoComplete="new-password"
              className={buyerInputCls(errOf("confirmPassword"), "pr-12")}
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
          {errOf("confirmPassword") ? (
            <p className="mt-1 flex items-center gap-1 text-xs text-red-500">
              <AlertCircle className="h-3 w-3" /> {errOf("confirmPassword")}
            </p>
          ) : (
            form.confirmPassword &&
            form.password &&
            form.password === form.confirmPassword && (
              <p className="mt-1 flex items-center gap-1 text-xs text-[#10B981]">
                <CheckCircle2 className="h-3 w-3" /> 密码匹配
              </p>
            )
          )}
        </div>

        <button
          type="submit"
          disabled={loading}
          className="mt-2 flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-[#003366] text-base font-semibold text-white shadow-sm transition-all hover:bg-[#002244] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-70"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              注册中...
            </>
          ) : (
            "注册采购方账户"
          )}
        </button>
      </form>
    </>
  );
}

interface BuyerFieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  onBlur: () => void;
  error: string | null;
  required?: boolean;
  hint?: string;
  footnote?: string;
  placeholder?: string;
  type?: string;
  autoComplete?: string;
  inputMode?: React.HTMLAttributes<HTMLInputElement>["inputMode"];
  maxLength?: number;
  extraInputClass?: string;
}

function BuyerField({
  id, label, value, onChange, onBlur, error, required, hint, footnote,
  placeholder, type = "text", autoComplete, inputMode, maxLength, extraInputClass = "",
}: BuyerFieldProps) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-sm font-semibold text-gray-700">
        {label}{required && " *"}
        {hint && <span className="ml-1 font-normal text-gray-400">{hint}</span>}
      </Label>
      <input
        id={id} name={id} type={type} value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
        placeholder={placeholder}
        autoComplete={autoComplete}
        inputMode={inputMode}
        maxLength={maxLength}
        className={buyerInputCls(error, extraInputClass)}
      />
      {error ? (
        <p className="text-xs text-red-500">{error}</p>
      ) : (
        footnote && <p className="text-xs text-gray-400">{footnote}</p>
      )}
    </div>
  );
}
