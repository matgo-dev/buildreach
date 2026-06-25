"use client";
// /register 入口:角色选择后:
// - BUYER → 坦桑尼亚场景单页表单(multipart/form-data,注册即登录)
// - SUPPLIER → 3 步向导(Step 1 国家 / Step 2 语言 / Step 3 表单)

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useRouter } from "@/i18n/navigation";
import { useLocale, useTranslations } from "next-intl";
import {
  AlertCircle,
  Building2,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Eye,
  EyeOff,
  ImagePlus,
  Loader2,
  ShoppingCart,
  X,
} from "lucide-react";

import { Label } from "@/components/ui/label";
import { authApi, type LoginResult } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import {
  validateEmail,
  validatePassword,
  validateRequired,
} from "@/lib/validators";
import type { CountryCode, LanguageCode } from "@/config/country-registration-rules";
import { Link } from "@/i18n/navigation";
import { LocaleSwitcher } from "@/components/i18n/LocaleSwitcher";
import { compressImage } from "@/lib/image-compress";

import { StepIndicator } from "./_components/StepIndicator";
import { StepCountry } from "./_components/StepCountry";
import { StepLanguage } from "./_components/StepLanguage";
import { StepForm } from "./_components/StepForm";
import { useRegisterDraft } from "./_components/useRegisterDraft";
import { useBeforeUnload } from "./_components/useBeforeUnload";
import { useAuthStore } from "@/stores/authStore";
import { defaultDashboardOf } from "@/config/navigation";
import { preferenceToLocale } from "@/i18n/locale-utils";
import { routing } from "@/i18n/routing";

type Role = "BUYER" | "SUPPLIER" | "";

const INPUT_BASE =
  "h-11 w-full rounded-lg border bg-white px-3 text-sm text-gray-800 placeholder-gray-400 transition-all focus:outline-none focus:ring-2";
const INPUT_OK_BUYER =
  "border-gray-200 focus:border-[#0D4D4D] focus:ring-[#0D4D4D]/15";
const INPUT_ERR =
  "border-red-400 focus:border-red-500 focus:ring-red-500/15";

function buyerInputCls(error: string | null, extra = ""): string {
  return `${INPUT_BASE} ${error ? INPUT_ERR : INPUT_OK_BUYER} ${extra}`;
}

// 手机号前端轻量校验(最终以后端 E.164 归一化为准)
const PHONE_REGION_CONFIG = {
  TZ: { dialCode: "+255", flag: "🇹🇿", label: "Tanzania", re: /^\d{9}$/, maxLen: 9, phKey: "ph_phone_tz", errKey: "err_phone_format_tz" },
  CN: { dialCode: "+86", flag: "🇨🇳", label: "China", re: /^1[3-9]\d{9}$/, maxLen: 11, phKey: "ph_phone_cn", errKey: "err_phone_format_cn" },
} as const;
type PhoneRegion = keyof typeof PHONE_REGION_CONFIG;
// 允许的上传格式
const ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_IMAGE_SIZE = 5 * 1024 * 1024; // 5MB

export default function RegisterPage() {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("buyerRegister");
  const tc = useTranslations("common");

  // 默认直接进入买方注册（供应商入口暂不暴露）
  const searchParams = useSearchParams();
  const urlRole = searchParams.get("role") || "";
  const [role, setRole] = useState<Role>(
    urlRole === "SUPPLIER" ? "SUPPLIER" : "BUYER",
  );
  // URL 参数变化时同步（切语言刷新后）
  useEffect(() => {
    if (urlRole === "SUPPLIER") {
      setRole("SUPPLIER");
    }
  }, [urlRole]);

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

  // 切换角色时清掉 SUPPLIER 草稿 + 同步到 URL（切语言后可恢复）
  const handleSwitchRole = (next: Role) => {
    if (role === "SUPPLIER" && next !== "SUPPLIER") clearDraft();
    setRole(next);
    // 同步到 URL query，不触发导航
    const url = new URL(window.location.href);
    if (next) url.searchParams.set("role", next);
    else url.searchParams.delete("role");
    window.history.replaceState({}, "", url.toString());
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

  // 注册成功后:存 token → 拉 me → 跳转 buyer 首页
  const handleBuyerRegistered = useCallback(async (tokens: LoginResult) => {
    const { setAccessToken, setUser, setLoaded } = useAuthStore.getState();
    setAccessToken(tokens.access_token);
    try {
      const me = await authApi.me();
      setUser(me);
      setLoaded(true);
      const targetLocale = preferenceToLocale(me.language_preference);
      const targetPath = defaultDashboardOf(me.roles);
      if (targetLocale !== locale && targetLocale !== routing.defaultLocale) {
        window.location.href = `/${targetLocale}${targetPath}`;
      } else if (locale !== routing.defaultLocale) {
        window.location.href = `/${locale}${targetPath}`;
      } else {
        router.replace(targetPath);
      }
    } catch {
      // me 失败:降级跳首页
      router.replace("/");
    }
  }, [locale, router]);

  return (
    <>
      <div className="mb-6 text-center">
        <h2 className="text-xl font-bold text-gray-900">{t("pageTitle")}</h2>
        {!role && (
          <p className="mt-1 text-sm text-gray-400">{t("selectRole")}</p>
        )}
      </div>

      {/* 角色选择 */}
      {!role && (
        <div className="mb-6">
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => handleSwitchRole("BUYER")}
              className="group flex flex-col items-center gap-3 rounded-xl border-2 border-gray-200 p-5 transition-all hover:border-[#0D4D4D] hover:bg-[#0D4D4D]/5"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50 transition-colors group-hover:bg-[#0D4D4D]/10">
                <ShoppingCart className="h-6 w-6 text-gray-400 transition-colors group-hover:text-[#0D4D4D]" />
              </div>
              <div className="text-center">
                <p className="text-sm font-semibold text-gray-700 transition-colors group-hover:text-[#0D4D4D]">
                  {t("roleBuyer")}
                </p>
                <p className="mt-0.5 text-xs text-gray-400">{t("roleBuyerHint")}</p>
              </div>
              <ChevronRight className="h-4 w-4 text-gray-300 transition-colors group-hover:text-[#0D4D4D]" />
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
                  {t("roleSupplier")}
                </p>
                <p className="mt-0.5 text-xs text-gray-400">{t("roleSupplierHint")}</p>
              </div>
              <ChevronRight className="h-4 w-4 text-gray-300 transition-colors group-hover:text-[#FF6B35]" />
            </button>
          </div>
        </div>
      )}

      {role && (
        <>

          {role === "BUYER" && <BuyerForm onSubmitted={handleBuyerRegistered} />}

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
          {t("hasAccount")}{" "}
          <Link href="/login" className="font-semibold text-[#FF6B35] transition-colors hover:text-[#e05a25]">
            {t("goLogin")}
          </Link>
        </p>
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
        <Loader2 className="h-6 w-6 animate-spin text-[#0D4D4D]" />
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

// ===== BUYER 坦桑尼亚注册表单(multipart/form-data,注册即自动登录) =====

interface BuyerFormProps {
  onSubmitted: (tokens: LoginResult) => void;
}

function BuyerForm({ onSubmitted }: BuyerFormProps) {
  const t = useTranslations("buyerRegister");
  const locale = useLocale();

  // 表单字段 — 中文环境默认 CN，其他默认 TZ
  const [phoneRegion, setPhoneRegion] = useState<PhoneRegion>(locale === "zh" ? "CN" : "TZ");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [address, setAddress] = useState("");
  const [email, setEmail] = useState("");
  const [storefrontImages, setStorefrontImages] = useState<File[]>([]);
  const [licenseImages, setLicenseImages] = useState<File[]>([]);

  // UI 状态
  const [showPassword, setShowPassword] = useState(false);
  const [submitError, setSubmitError] = useState<React.ReactNode>("");
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string | null>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const [optionalExpanded, setOptionalExpanded] = useState(false);

  // 缩略图预览 URL 管理
  const [sfPreviews, setSfPreviews] = useState<string[]>([]);
  const [licPreviews, setLicPreviews] = useState<string[]>([]);
  // 图片放大预览
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [legalModal, setLegalModal] = useState<"terms" | "privacy" | null>(null);
  const sfInputRef = useRef<HTMLInputElement>(null);
  const licInputRef = useRef<HTMLInputElement>(null);

  // storefrontImages 变化时更新预览
  useEffect(() => {
    const urls = storefrontImages.map((f) => URL.createObjectURL(f));
    setSfPreviews(urls);
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [storefrontImages]);

  useEffect(() => {
    const urls = licenseImages.map((f) => URL.createObjectURL(f));
    setLicPreviews(urls);
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [licenseImages]);

  // 校验单个字段
  const validateField = (field: string): string | null => {
    switch (field) {
      case "phone":
        if (!phone) return t("err_phone_required");
        if (!PHONE_REGION_CONFIG[phoneRegion].re.test(phone)) return t(PHONE_REGION_CONFIG[phoneRegion].errKey);
        return null;
      case "password":
        return validatePassword(password);
      case "name":
        return validateRequired(name, t("label_name"));
      case "companyName":
        return validateRequired(companyName, t("label_company"));
      case "address":
        return validateRequired(address, t("label_address"));
      case "email":
        return validateEmail(email);
      case "storefrontImages":
        if (storefrontImages.length === 0) return t("err_storefront_required");
        return null;
      default:
        return null;
    }
  };

  const touch = (field: string) => {
    setTouched((t) => ({ ...t, [field]: true }));
    setErrors((e) => ({ ...e, [field]: validateField(field) }));
  };

  const errOf = (field: string): string | null =>
    touched[field] ? errors[field] ?? null : null;

  // 全字段校验
  const validateAll = (): string | null => {
    const fields = ["phone", "password", "name", "companyName", "address", "email", "storefrontImages"];
    const newErrors: Record<string, string | null> = {};
    const newTouched: Record<string, boolean> = {};
    let firstError: string | null = null;
    let firstErrorField: string | null = null;
    for (const f of fields) {
      newTouched[f] = true;
      const err = validateField(f);
      newErrors[f] = err;
      if (err && !firstError) {
        firstError = err;
        firstErrorField = f;
      }
    }
    setTouched((t) => ({ ...t, ...newTouched }));
    setErrors((e) => ({ ...e, ...newErrors }));
    // 滚动到第一个错误字段
    if (firstErrorField) {
      const el = document.getElementById(`field-${firstErrorField}`);
      el?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    return firstError;
  };

  // 文件校验（只检格式，大小由自动压缩处理）
  const validateImageFile = (file: File): string | null => {
    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) return t("err_image_format");
    return null;
  };

  // 添加店面照片（自动压缩）
  const handleStorefrontAdd = async (files: FileList | null) => {
    if (!files) return;
    const newFiles: File[] = [];
    for (let i = 0; i < files.length; i++) {
      const err = validateImageFile(files[i]);
      if (err) {
        setErrors((e) => ({ ...e, storefrontImages: err }));
        setTouched((t) => ({ ...t, storefrontImages: true }));
        return;
      }
      newFiles.push(await compressImage(files[i]));
    }
    const combined = [...storefrontImages, ...newFiles].slice(0, 10);
    setStorefrontImages(combined);
    if (combined.length > 0) {
      setErrors((e) => ({ ...e, storefrontImages: null }));
    }
  };

  const removeStorefrontImage = (idx: number) => {
    setStorefrontImages((prev) => prev.filter((_, i) => i !== idx));
  };

  // 添加执照照片（自动压缩）
  const handleLicenseAdd = async (files: FileList | null) => {
    if (!files) return;
    const newFiles: File[] = [];
    for (let i = 0; i < files.length; i++) {
      const err = validateImageFile(files[i]);
      if (err) {
        setErrors((e) => ({ ...e, licenseImages: err }));
        setTouched((t) => ({ ...t, licenseImages: true }));
        return;
      }
      newFiles.push(await compressImage(files[i]));
    }
    setLicenseImages((prev) => [...prev, ...newFiles]);
  };

  const removeLicenseImage = (idx: number) => {
    setLicenseImages((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const v = validateAll();
    if (v) return;
    setSubmitError("");
    setLoading(true);
    try {
      const tokens = await authApi.registerBuyer({
        phone,
        phone_region: phoneRegion,
        password,
        name,
        company_name: companyName,
        address,
        email,
        storefront_images: storefrontImages,
        license_images: licenseImages.length > 0 ? licenseImages : undefined,
        language_preference: locale,
      });
      onSubmitted(tokens);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === 40921) {
          setErrors((e) => ({ ...e, phone: err.message }));
          setTouched((t) => ({ ...t, phone: true }));
        } else if (err.code === 40922) {
          setErrors((e) => ({ ...e, email: err.message }));
          setTouched((t) => ({ ...t, email: true }));
        } else {
          setSubmitError(err.message);
        }
      } else {
        setSubmitError(t("err_generic"));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* 后端业务错误（非字段级） */}
      {submitError && (
        <div className="mb-5 flex items-center gap-2.5 rounded-lg border-l-4 border-red-500 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{submitError}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4" noValidate autoComplete="off">
        {/* 隐藏陷阱：吸收浏览器 autofill，防止覆盖手机号 */}
        <input type="text" name="hidden_username" autoComplete="username" className="hidden" tabIndex={-1} aria-hidden="true" />
        <input type="password" name="hidden_password" autoComplete="new-password" className="hidden" tabIndex={-1} aria-hidden="true" />
        {/* 1. Name */}
        <div className="space-y-1.5" id="field-name">
          <Label htmlFor="name" className="text-sm font-semibold text-gray-700">
            {t("label_name")} <span className="text-red-500">*</span>
          </Label>
          <input
            id="name" name="name" type="text"
            value={name}
            onChange={(e) => { setName(e.target.value); if (errors.name) setErrors((err) => ({ ...err, name: null })); }}
            onBlur={() => touch("name")}
            placeholder={t("ph_name")}
            className={buyerInputCls(errOf("name"))}
          />
          {errOf("name") && <p className="text-xs text-red-500">{errOf("name")}</p>}
        </div>

        {/* 2. Shop / Company Name */}
        <div className="space-y-1.5" id="field-companyName">
          <Label htmlFor="companyName" className="text-sm font-semibold text-gray-700">
            {t("label_company")} <span className="text-red-500">*</span>
          </Label>
          <input
            id="companyName" name="companyName" type="text"
            value={companyName}
            onChange={(e) => { setCompanyName(e.target.value); if (errors.companyName) setErrors((err) => ({ ...err, companyName: null })); }}
            onBlur={() => touch("companyName")}
            placeholder={t("ph_company")}
            className={buyerInputCls(errOf("companyName"))}
          />
          {errOf("companyName") && <p className="text-xs text-red-500">{errOf("companyName")}</p>}
        </div>

        {/* 3. Phone / WhatsApp */}
        <div className="space-y-1.5" id="field-phone">
          <Label htmlFor="phone" className="text-sm font-semibold text-gray-700">
            {t("label_phone")} <span className="text-red-500">*</span>
          </Label>
          <div className="flex">
            <select
              value={phoneRegion}
              onChange={(e) => {
                const newRegion = e.target.value as PhoneRegion;
                setPhoneRegion(newRegion);
                setPhone((prev) => prev.slice(0, PHONE_REGION_CONFIG[newRegion].maxLen));
                if (errors.phone) setErrors((er) => ({ ...er, phone: null }));
              }}
              className="inline-flex items-center rounded-l-lg border border-r-0 border-gray-200 bg-gray-50 px-2 text-sm text-gray-600 focus:outline-none"
            >
              {(Object.keys(PHONE_REGION_CONFIG) as PhoneRegion[]).map((r) => (
                <option key={r} value={r}>
                  {PHONE_REGION_CONFIG[r].flag} {PHONE_REGION_CONFIG[r].dialCode}
                </option>
              ))}
            </select>
            <input
              id="phone" name="phone" type="tel"
              value={phone}
              onChange={(e) => {
                const v = e.target.value.replace(/\D/g, "").slice(0, PHONE_REGION_CONFIG[phoneRegion].maxLen);
                setPhone(v);
                if (errors.phone) setErrors((er) => ({ ...er, phone: null }));
              }}
              onBlur={() => touch("phone")}
              placeholder={t(PHONE_REGION_CONFIG[phoneRegion].phKey)}
              inputMode="numeric"
              autoComplete="off"
              className={buyerInputCls(errOf("phone"), "rounded-l-none")}
            />
          </div>
          {errOf("phone") && <p className="text-xs text-red-500">{errOf("phone")}</p>}
        </div>

        {/* 4. Email */}
        <div className="space-y-1.5" id="field-email">
          <Label htmlFor="email" className="text-sm font-semibold text-gray-700">
            {t("label_email")} <span className="text-red-500">*</span>
          </Label>
          <input
            id="email" name="email" type="email"
            value={email}
            onChange={(e) => { setEmail(e.target.value); if (errors.email) setErrors((err) => ({ ...err, email: null })); }}
            onBlur={() => touch("email")}
            placeholder={t("ph_email")}
            autoComplete="email"
            className={buyerInputCls(errOf("email"))}
          />
          {errOf("email") && <p className="text-xs text-red-500">{errOf("email")}</p>}
        </div>

        {/* 5. Password */}
        <div className="space-y-1.5" id="field-password">
          <Label htmlFor="password" className="text-sm font-semibold text-gray-700">
            {t("label_password")} <span className="text-red-500">*</span>
          </Label>
          <div className="relative">
            <input
              id="password" name="password"
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                if (errors.password) setErrors((err) => ({ ...err, password: null }));
              }}
              onBlur={() => touch("password")}
              placeholder={t("ph_password")}
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
          <p className="mt-1 text-[11px] text-gray-400">{t("pwd_hint_simple")}</p>
        </div>

        {/* 6. Address */}
        <div className="space-y-1.5" id="field-address">
          <Label htmlFor="address" className="text-sm font-semibold text-gray-700">
            {t("label_address")} <span className="text-red-500">*</span>
          </Label>
          <input
            id="address" name="address" type="text"
            value={address}
            onChange={(e) => { setAddress(e.target.value); if (errors.address) setErrors((err) => ({ ...err, address: null })); }}
            onBlur={() => touch("address")}
            placeholder={t("ph_address")}
            className={buyerInputCls(errOf("address"))}
          />
          {errOf("address") && <p className="text-xs text-red-500">{errOf("address")}</p>}
        </div>

        {/* 4. Storefront Photos (required) */}
        <div className="space-y-1.5" id="field-storefrontImages">
          <Label className="text-sm font-semibold text-gray-700">
            {t("label_storefront")} <span className="text-red-500">*</span>
          </Label>
          <p className="text-xs text-gray-400">{t("storefront_hint")}</p>
          <div className="flex flex-wrap gap-2">
            {sfPreviews.map((url, idx) => (
              <div key={idx} className="relative h-20 w-20 overflow-hidden rounded-lg border border-gray-200">
                <img
                  src={url} alt="" className="h-full w-full cursor-pointer object-cover"
                  onClick={() => setPreviewUrl(url)}
                />
                <button
                  type="button"
                  onClick={() => removeStorefrontImage(idx)}
                  className="absolute right-0.5 top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-black/50 text-white hover:bg-black/70"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            ))}
            {storefrontImages.length < 10 && (
              <button
                type="button"
                onClick={() => sfInputRef.current?.click()}
                className="flex h-20 w-20 flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed border-gray-300 text-gray-400 transition-colors hover:border-[#0D4D4D] hover:text-[#0D4D4D]"
              >
                <ImagePlus className="h-5 w-5" />
                <span className="text-[10px]">{t("upload")}</span>
              </button>
            )}
          </div>
          <input
            ref={sfInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            className="hidden"
            onChange={(e) => { handleStorefrontAdd(e.target.files); e.target.value = ""; }}
          />
          {errOf("storefrontImages") && <p className="text-xs text-red-500">{errOf("storefrontImages")}</p>}
        </div>

        {/* 可折叠选填区域 */}
        <div className="rounded-lg border border-gray-200">
          <button
            type="button"
            onClick={() => setOptionalExpanded((v) => !v)}
            className="flex w-full items-center justify-between px-4 py-3 text-sm text-gray-500 transition-colors hover:bg-gray-50"
          >
            <span>{t("optional_section")}</span>
            {optionalExpanded
              ? <ChevronUp className="h-4 w-4" />
              : <ChevronDown className="h-4 w-4" />
            }
          </button>
          {optionalExpanded && (
            <div className="space-y-4 border-t border-gray-100 px-4 pb-4 pt-3">
              {/* License Images */}
              <div className="space-y-1.5" id="field-licenseImages">
                <Label className="text-sm font-semibold text-gray-700">
                  {t("label_license")}
                </Label>
                <p className="text-xs text-gray-400">{t("license_hint")}</p>
                <div className="flex flex-wrap gap-2">
                  {licPreviews.map((url, idx) => (
                    <div key={idx} className="relative h-20 w-20 overflow-hidden rounded-lg border border-gray-200">
                      <img
                        src={url} alt="" className="h-full w-full cursor-pointer object-cover"
                        onClick={() => setPreviewUrl(url)}
                      />
                      <button
                        type="button"
                        onClick={() => removeLicenseImage(idx)}
                        className="absolute right-0.5 top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-black/50 text-white hover:bg-black/70"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  ))}
                  <button
                    type="button"
                    onClick={() => licInputRef.current?.click()}
                    className="flex h-20 w-20 flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed border-gray-300 text-gray-400 transition-colors hover:border-[#0D4D4D] hover:text-[#0D4D4D]"
                  >
                    <ImagePlus className="h-5 w-5" />
                    <span className="text-[10px]">{t("upload")}</span>
                  </button>
                </div>
                <input
                  ref={licInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  multiple
                  className="hidden"
                  onChange={(e) => { handleLicenseAdd(e.target.files); e.target.value = ""; }}
                />
                {errOf("licenseImages") && <p className="text-xs text-red-500">{errOf("licenseImages")}</p>}
              </div>

            </div>
          )}
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={loading}
          className="mt-2 flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-[#0D4D4D] text-base font-semibold text-white shadow-sm transition-all hover:bg-[#0a3d3d] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-70"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              {t("submitting")}
            </>
          ) : (
            t("submit")
          )}
        </button>

        {/* 服务条款 */}
        <p className="text-center text-xs text-gray-400">
          {t("terms_prefix")}{" "}
          <button type="button" onClick={() => setLegalModal("terms")} className="text-[#00505a] underline hover:text-[#003d3d]">{t("terms_link")}</button>
          {" "}{t("terms_and")}{" "}
          <button type="button" onClick={() => setLegalModal("privacy")} className="text-[#00505a] underline hover:text-[#003d3d]">{t("terms_privacy_link")}</button>
        </p>
      </form>

      {/* 图片放大预览弹窗 */}
      {previewUrl && (
        <div
          className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/70 p-4"
          onClick={() => setPreviewUrl(null)}
        >
          <div className="relative max-h-[85vh] max-w-[85vw]">
            <img src={previewUrl} alt="" className="max-h-[85vh] max-w-[85vw] rounded-lg object-contain" />
            <button
              type="button"
              onClick={() => setPreviewUrl(null)}
              className="absolute -right-3 -top-3 flex h-8 w-8 items-center justify-center rounded-full bg-white text-gray-700 shadow-lg hover:bg-gray-100"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* 服务条款 / 隐私政策弹窗 */}
      {legalModal && (
        <LegalModal type={legalModal} onClose={() => setLegalModal(null)} />
      )}
    </>
  );
}

/** 服务条款/隐私政策模态弹窗 */
function LegalModal({ type, onClose }: { type: "terms" | "privacy"; onClose: () => void }) {
  const tLegal = useTranslations("legal");
  const t = useTranslations("buyerRegister");
  const sectionCount = type === "terms" ? 8 : 7;
  const sections = Array.from({ length: sectionCount }, (_, i) => ({
    title: tLegal(`${type}.s${i + 1}_title`),
    content: tLegal(`${type}.s${i + 1}_content`),
  }));

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 p-4">
      <div className="relative flex w-full max-w-2xl max-h-[85vh] flex-col rounded-xl bg-white shadow-2xl">
        {/* 头部 */}
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h2 className="text-lg font-bold text-[#00505a]">{tLegal(`${type}.title`)}</h2>
          <button type="button" onClick={onClose} className="rounded-full p-1 hover:bg-gray-100">
            <X className="h-5 w-5 text-gray-500" />
          </button>
        </div>
        {/* 可滚动内容 */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          <p className="text-xs text-gray-400">{tLegal(`${type}.lastUpdated`)}</p>
          {sections.map((s, i) => (
            <section key={i}>
              <h3 className="text-sm font-bold text-gray-800 mb-1.5">{`${i + 1}. ${s.title}`}</h3>
              <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-line">{s.content}</p>
            </section>
          ))}
        </div>
        {/* 底部按钮 */}
        <div className="border-t px-6 py-4">
          <button
            type="button"
            onClick={onClose}
            className="w-full rounded-lg bg-[#e3a615] py-2.5 text-sm font-bold text-white transition-colors hover:bg-[#c99012]"
          >
            {t("legalReadDone")}
          </button>
        </div>
      </div>
    </div>
  );
}
