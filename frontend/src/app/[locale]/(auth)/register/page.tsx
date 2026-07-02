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
  Check,
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
import { categoriesApi, type CategoryNode } from "@/lib/api/categories";
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
import { useAuthConfig } from "@/hooks/usePublicConfig";
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

// 允许的上传格式
const ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];

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
  const tc = useTranslations("common");
  const locale = useLocale();

  // 邮箱验证开关(后端 REQUIRE_EMAIL_VERIFICATION)。加载中(undefined)按安全默认视为开启。
  const { requireEmailVerification, isLoading: authCfgLoading } = useAuthConfig();
  const emailVerificationOn = requireEmailVerification !== false;

  // 必填字段
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [verificationToken, setVerificationToken] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [whatsapp, setWhatsapp] = useState("");

  // 选填字段（企业信息区）
  const [companyName, setCompanyName] = useState("");
  const [address, setAddress] = useState("");
  const [storefrontImages, setStorefrontImages] = useState<File[]>([]);
  const [licenseImages, setLicenseImages] = useState<File[]>([]);

  // 验证码发送状态
  const [codeSending, setCodeSending] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  // UI 状态
  const [showPassword, setShowPassword] = useState(false);
  const [submitError, setSubmitError] = useState<React.ReactNode>("");
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string | null>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  // 可选品类区（折叠展开）
  const [categories, setCategories] = useState<CategoryNode[]>([]);
  const [catLoading, setCatLoading] = useState(false);
  const [catExpanded, setCatExpanded] = useState(false);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [companySectionExpanded, setCompanySectionExpanded] = useState(false);
  const COLLAPSED_CAT_COUNT = 6;

  // 缩略图预览 URL 管理
  const [sfPreviews, setSfPreviews] = useState<string[]>([]);
  const [licPreviews, setLicPreviews] = useState<string[]>([]);
  // 图片放大预览
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [legalModal, setLegalModal] = useState<"terms" | "privacy" | null>(null);
  const sfInputRef = useRef<HTMLInputElement>(null);
  const licInputRef = useRef<HTMLInputElement>(null);
  const cooldownRef = useRef<ReturnType<typeof setInterval> | null>(null);

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

  // 组件卸载时清理冷却计时器，防止内存泄露
  useEffect(() => {
    return () => {
      if (cooldownRef.current) clearInterval(cooldownRef.current);
    };
  }, []);

  // 挂载时加载品类列表
  useEffect(() => {
    setCatLoading(true);
    categoriesApi.list({ level: 1 }).then((data) => {
      setCategories(data);
      setCatLoading(false);
    }).catch(() => setCatLoading(false));
  }, []);

  // 发送验证码
  const handleSendCode = async () => {
    const emailErr = validateEmail(email, {
      required: tc("err_email_required"),
      format: tc("err_email_format"),
      domain: tc("err_email_domain"),
    });
    if (emailErr) {
      setErrors((e) => ({ ...e, email: emailErr }));
      setTouched((t) => ({ ...t, email: true }));
      return;
    }
    setCodeSending(true);
    try {
      await authApi.sendVerificationCode(email, "REGISTER");
      setCooldown(60);
      if (cooldownRef.current) clearInterval(cooldownRef.current);
      cooldownRef.current = setInterval(() => {
        setCooldown((prev) => {
          if (prev <= 1) { clearInterval(cooldownRef.current!); cooldownRef.current = null; return 0; }
          return prev - 1;
        });
      }, 1000);
    } catch (err) {
      if (err instanceof ApiError) {
        // 40104: 冷却中(后端返回剩余秒数)
        if (err.code === 40104) {
          const seconds = (err.data as { remaining_seconds?: number })?.remaining_seconds ?? 60;
          setErrors((e) => ({ ...e, verificationCode: t("err_cooldown", { seconds }) }));
          setTouched((te) => ({ ...te, verificationCode: true }));
          // 同步冷却倒计时
          setCooldown(seconds);
          if (cooldownRef.current) clearInterval(cooldownRef.current);
          cooldownRef.current = setInterval(() => {
            setCooldown((prev) => {
              if (prev <= 1) { clearInterval(cooldownRef.current!); cooldownRef.current = null; return 0; }
              return prev - 1;
            });
          }, 1000);
        } else if (err.code === 40105) {
          setErrors((e) => ({ ...e, verificationCode: t("err_rate_limit") }));
          setTouched((te) => ({ ...te, verificationCode: true }));
        } else {
          setErrors((e) => ({ ...e, verificationCode: t("code_send_failed") }));
          setTouched((te) => ({ ...te, verificationCode: true }));
        }
      } else {
        setErrors((e) => ({ ...e, verificationCode: t("code_send_failed") }));
        setTouched((te) => ({ ...te, verificationCode: true }));
      }
    } finally {
      setCodeSending(false);
    }
  };

  // 校验验证码并获取 verification_token；返回 token 字符串或 null（失败）
  const handleVerifyCode = async (): Promise<string | null> => {
    if (!verificationCode.trim()) {
      setErrors((e) => ({ ...e, verificationCode: t("err_code_invalid") }));
      setTouched((te) => ({ ...te, verificationCode: true }));
      return null;
    }
    try {
      const { verification_token } = await authApi.verifyVerificationCode(
        email, verificationCode, "REGISTER",
      );
      setVerificationToken(verification_token);
      setErrors((e) => ({ ...e, verificationCode: null }));
      return verification_token;
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === 40101) {
          setErrors((e) => ({ ...e, verificationCode: t("err_code_invalid") }));
        } else if (err.code === 40102) {
          setErrors((e) => ({ ...e, verificationCode: t("err_code_expired") }));
        } else if (err.code === 40103) {
          setErrors((e) => ({ ...e, verificationCode: t("err_code_max_attempts") }));
        } else {
          setErrors((e) => ({ ...e, verificationCode: t("err_code_invalid") }));
        }
      } else {
        setErrors((e) => ({ ...e, verificationCode: t("err_code_invalid") }));
      }
      setTouched((te) => ({ ...te, verificationCode: true }));
      return null;
    }
  };

  // 校验单个字段
  const validateField = (field: string): string | null => {
    switch (field) {
      case "name":
        return validateRequired(name, t("label_name"));
      case "email":
        return validateEmail(email, {
          required: tc("err_email_required"),
          format: tc("err_email_format"),
          domain: tc("err_email_domain"),
        });
      case "verificationCode":
        if (!verificationCode.trim()) return t("err_code_invalid");
        return null;
      case "password":
        return validatePassword(password);
      case "phone":
        if (!phone.trim()) return t("err_phone_required");
        return null;
      case "whatsapp":
        if (!whatsapp.trim()) return t("err_phone_required");
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

  // 全必填字段校验
  const validateAll = (): string | null => {
    const fields = emailVerificationOn
      ? ["name", "email", "verificationCode", "password", "phone", "whatsapp"]
      : ["name", "email", "password", "phone", "whatsapp"];
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
      // 邮箱验证开启时:确保有 verification_token（handleVerifyCode 直接返回 token 字符串）。
      // 关闭时:跳过验证码流程,注册不带 token。
      let token = verificationToken;
      if (emailVerificationOn && !token) {
        const result = await handleVerifyCode();
        if (!result) { setLoading(false); return; }
        token = result;
      }
      const tokens = await authApi.registerBuyer({
        name,
        email,
        verification_token: emailVerificationOn ? token : undefined,
        password,
        phone,
        whatsapp,
        company_name: companyName || undefined,
        address: address || undefined,
        business_category_codes: selectedCategories.length > 0 ? selectedCategories : undefined,
        storefront_images: storefrontImages.length > 0 ? storefrontImages : undefined,
        license_images: licenseImages.length > 0 ? licenseImages : undefined,
        language_preference: locale,
      });
      onSubmitted(tokens);
    } catch (err) {
      if (err instanceof ApiError) {
        // 40106: verification_token 失效，需重新验证
        if (err.code === 40106) {
          setVerificationToken("");
          setErrors((e) => ({ ...e, verificationCode: t("err_token_invalid") }));
          setTouched((te) => ({ ...te, verificationCode: true }));
          return;
        }
        // 解析 data.errors 数组，将每个字段错误映射到表单
        const fieldErrors = (err.data as { errors?: { field: string; code: number; message: string }[] })?.errors;
        if (fieldErrors && fieldErrors.length > 0) {
          const codeToI18n: Record<number, string> = {
            40921: t("err_phone_exists"),
            40922: t("err_email_exists"),
          };
          let hasFieldMatch = false;
          for (const fe of fieldErrors) {
            const msg = codeToI18n[fe.code] || fe.message;
            if (fe.field === "phone") {
              setErrors((e) => ({ ...e, phone: msg }));
              setTouched((t) => ({ ...t, phone: true }));
              hasFieldMatch = true;
            } else if (fe.field === "email") {
              setErrors((e) => ({ ...e, email: msg }));
              setTouched((t) => ({ ...t, email: true }));
              hasFieldMatch = true;
            }
          }
          if (!hasFieldMatch) {
            setSubmitError(err.message);
          } else {
            const firstField = fieldErrors.find((fe) => fe.field === "phone" || fe.field === "email")?.field;
            if (firstField) {
              const el = document.getElementById(`field-${firstField}`);
              el?.scrollIntoView({ behavior: "smooth", block: "center" });
            }
          }
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

      <form onSubmit={handleSubmit} className="space-y-3" noValidate autoComplete="off">
        {/* 隐藏陷阱：吸收浏览器 autofill */}
        <input type="text" name="hidden_username" autoComplete="username" className="hidden" tabIndex={-1} aria-hidden="true" />
        <input type="password" name="hidden_password" autoComplete="new-password" className="hidden" tabIndex={-1} aria-hidden="true" />

        {/* 1. 姓名 */}
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

        {/* 2. 邮箱 + 发送验证码按钮 */}
        <div className="space-y-1.5" id="field-email">
          <Label htmlFor="email" className="text-sm font-semibold text-gray-700">
            {t("email_label")} <span className="text-red-500">*</span>
          </Label>
          <div className="flex gap-2">
            <input
              id="email" name="email" type="email"
              value={email}
              onChange={(e) => { setEmail(e.target.value); if (errors.email) setErrors((err) => ({ ...err, email: null })); }}
              onBlur={() => touch("email")}
              placeholder={t("email_placeholder")}
              autoComplete="email"
              className={buyerInputCls(errOf("email"), "flex-1")}
            />
            {emailVerificationOn && (
              <button
                type="button"
                onClick={handleSendCode}
                disabled={cooldown > 0 || codeSending}
                className="shrink-0 rounded-lg border border-[#0D4D4D] px-3 text-sm font-medium text-[#0D4D4D] transition-all hover:bg-[#0D4D4D]/5 disabled:cursor-not-allowed disabled:border-gray-200 disabled:text-gray-400"
              >
                {codeSending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : cooldown > 0 ? (
                  t("resend_code", { seconds: cooldown })
                ) : (
                  t("send_code")
                )}
              </button>
            )}
          </div>
          {errOf("email") && <p className="text-xs text-red-500">{errOf("email")}</p>}
        </div>

        {/* 3. 验证码(仅在邮箱验证开启时显示) */}
        {emailVerificationOn && (
          <div className="space-y-1.5" id="field-verificationCode">
            <Label htmlFor="verificationCode" className="text-sm font-semibold text-gray-700">
              {t("verification_code_label")} <span className="text-red-500">*</span>
            </Label>
            <input
              id="verificationCode" name="verificationCode" type="text"
              value={verificationCode}
              onChange={(e) => {
                const v = e.target.value.replace(/\D/g, "").slice(0, 6);
                setVerificationCode(v);
                // 输入满 6 位时清除 token（需重新验证）
                if (v !== verificationCode) setVerificationToken("");
                if (errors.verificationCode) setErrors((err) => ({ ...err, verificationCode: null }));
              }}
              onBlur={() => touch("verificationCode")}
              placeholder={t("verification_code_placeholder")}
              inputMode="numeric"
              maxLength={6}
              autoComplete="one-time-code"
              className={buyerInputCls(errOf("verificationCode"), "tracking-widest")}
            />
            {errOf("verificationCode") && <p className="text-xs text-red-500">{errOf("verificationCode")}</p>}
            {/* 发送成功提示 */}
            {cooldown > 0 && !errOf("verificationCode") && (
              <p className="text-xs text-green-600">{t("code_sent")}</p>
            )}
          </div>
        )}

        {/* 4. 密码 */}
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

        {/* 5. 手机号（纯文本，无区号选择器） */}
        <div className="space-y-1.5" id="field-phone">
          <Label htmlFor="phone" className="text-sm font-semibold text-gray-700">
            {t("phone_label")} <span className="text-red-500">*</span>
          </Label>
          <input
            id="phone" name="phone" type="tel"
            value={phone}
            onChange={(e) => { setPhone(e.target.value); if (errors.phone) setErrors((err) => ({ ...err, phone: null })); }}
            onBlur={() => touch("phone")}
            placeholder=""
            autoComplete="tel"
            className={buyerInputCls(errOf("phone"))}
          />
          {errOf("phone") && <p className="text-xs text-red-500">{errOf("phone")}</p>}
        </div>

        {/* 6. WhatsApp */}
        <div className="space-y-1.5" id="field-whatsapp">
          <Label htmlFor="whatsapp" className="text-sm font-semibold text-gray-700">
            {t("whatsapp_label")} <span className="text-red-500">*</span>
          </Label>
          <input
            id="whatsapp" name="whatsapp" type="tel"
            value={whatsapp}
            onChange={(e) => { setWhatsapp(e.target.value); if (errors.whatsapp) setErrors((err) => ({ ...err, whatsapp: null })); }}
            onBlur={() => touch("whatsapp")}
            placeholder=""
            autoComplete="tel"
            className={buyerInputCls(errOf("whatsapp"))}
          />
          {errOf("whatsapp") && <p className="text-xs text-red-500">{errOf("whatsapp")}</p>}
        </div>

        {/* ---- 经营品类（选填，不折叠）---- */}
        <div className="mt-2 border-t border-gray-200 pt-3">
          <div className="space-y-1.5" id="field-categories">
            <Label className="text-sm font-semibold text-gray-700">
              {t("label_categories")}
            </Label>
            {catLoading ? (
              <div className="flex items-center gap-2 py-2 text-sm text-gray-400">
                <Loader2 className="h-4 w-4 animate-spin" /> {t("loading_categories")}
              </div>
            ) : categories.length > 0 ? (
              <>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {(catExpanded ? categories : categories.slice(0, COLLAPSED_CAT_COUNT)).map((cat) => {
                    const selected = selectedCategories.includes(cat.code);
                    const displayName = locale === "en" ? (cat.name_en || cat.name_zh) : locale === "sw" ? (cat.name_en || cat.name_zh) : cat.name_zh;
                    return (
                      <button
                        key={cat.code}
                        type="button"
                        onClick={() => setSelectedCategories((prev) =>
                          prev.includes(cat.code) ? prev.filter((c) => c !== cat.code) : [...prev, cat.code]
                        )}
                        className={
                          "flex items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-all " +
                          (selected
                            ? "border-[#0D4D4D] bg-[#0D4D4D]/5 text-[#0D4D4D] font-medium"
                            : "border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50")
                        }
                      >
                        <div className={
                          "flex h-4 w-4 shrink-0 items-center justify-center rounded border " +
                          (selected ? "border-[#0D4D4D] bg-[#0D4D4D] text-white" : "border-gray-300")
                        }>
                          {selected && <Check className="h-3 w-3" />}
                        </div>
                        <span className="truncate">{displayName}</span>
                      </button>
                    );
                  })}
                </div>
                {categories.length > COLLAPSED_CAT_COUNT && (
                  <button
                    type="button"
                    onClick={() => setCatExpanded((v) => !v)}
                    className="mt-2 flex w-full items-center justify-center gap-1 rounded-lg border border-gray-200 py-1.5 text-xs text-gray-500 transition-colors hover:bg-gray-50 hover:text-gray-700"
                  >
                    {catExpanded ? (
                      <>{t("collapse_categories")} <ChevronUp className="h-3.5 w-3.5" /></>
                    ) : (
                      <>{t("expand_categories", { count: categories.length - COLLAPSED_CAT_COUNT })} <ChevronDown className="h-3.5 w-3.5" /></>
                    )}
                  </button>
                )}
              </>
            ) : null}
          </div>
        </div>

        {/* ---- 补充信息（选填，折叠）---- */}
        <div className="rounded-lg border border-gray-200">
          <button
            type="button"
            onClick={() => setCompanySectionExpanded((v) => !v)}
            className="flex w-full items-center justify-between px-4 py-3 text-sm text-gray-500 transition-colors hover:bg-gray-50"
          >
            <span>{t("optional_section")}</span>
            {companySectionExpanded
              ? <ChevronUp className="h-4 w-4" />
              : <ChevronDown className="h-4 w-4" />
            }
          </button>
          {companySectionExpanded && (
            <div className="space-y-3 border-t border-gray-100 px-4 pb-4 pt-3">
              {/* 公司名称 */}
              <div className="space-y-1.5" id="field-companyName">
                <Label htmlFor="companyName" className="text-sm font-semibold text-gray-700">
                  {t("label_company")}
                </Label>
                <input
                  id="companyName" name="companyName" type="text"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  placeholder={t("ph_company")}
                  className={buyerInputCls(null)}
                />
              </div>

              {/* 地址 */}
              <div className="space-y-1.5" id="field-address">
                <Label htmlFor="address" className="text-sm font-semibold text-gray-700">
                  {t("label_address")}
                </Label>
                <input
                  id="address" name="address" type="text"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  placeholder={t("ph_address")}
                  className={buyerInputCls(null)}
                />
              </div>

              {/* 店面照片 */}
              <div className="space-y-1.5" id="field-storefrontImages">
                <Label className="text-sm font-semibold text-gray-700">
                  {t("label_storefront")}
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

              {/* 营业执照 */}
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
          disabled={loading || authCfgLoading}
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
  const sectionCount = type === "terms" ? 16 : 15;
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
