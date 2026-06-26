"use client";

// 3 步向导 Step 3:注册表单。
// - 顶部展示当前国家 + 凭证规则(只读)
// - registration_no 字段右上角徽章显示 country code(如 MY / SA)
// - 用 country.regNo.transform 规整输入(CN 自动大写截 18 位,数字国家剔除非数字)
// - blur 用 country.regNo.regex 校验
// - 密码不存任何持久化路径(useRegisterDraft 已防御)

import { useMemo, useState } from "react";
import { AlertCircle, CheckCircle2, Eye, EyeOff, Loader2 } from "lucide-react";

import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { authApi } from "@/lib/auth";
import {
  validateAllRegisterFields,
  validateEmail,
  validatePassword,
  validatePasswordConfirm,
  validateRegistrationNoByCountry,
  validateRequired,
  validateSupplierPhone,
} from "@/lib/validators";
import {
  getCountryByCode,
  multipleValidationBannerMessage,
  type CountryCode,
  type LanguageCode,
  type RegistrationFieldError,
} from "@/config/country-registration-rules";

type FieldName =
  | "company_name"
  | "registration_no"
  | "name"
  | "phone"
  | "email"
  | "password"
  | "confirmPassword";

interface StepFormProps {
  countryCode: CountryCode;
  languagePreference: LanguageCode;
  draft: {
    company_name: string;
    registration_no: string;
    name: string;
    phone: string;
    email: string;
  };
  updateDraft: (patch: Partial<StepFormProps["draft"]>) => void;
  onBack: () => void;
  onSubmitted: () => void;
}

const INPUT_BASE =
  "h-11 w-full rounded-lg border bg-white px-3 text-sm text-gray-800 placeholder-gray-400 transition-all focus:outline-none focus:ring-2";
const INPUT_OK =
  "border-gray-200 focus:border-[#FF6B35] focus:ring-[#FF6B35]/15";
const INPUT_ERR = "border-red-400 focus:border-red-500 focus:ring-red-500/15";

function cls(err: string | null, extra = "") {
  return `${INPUT_BASE} ${err ? INPUT_ERR : INPUT_OK} ${extra}`;
}

// Pydantic 英文错误 → 中文映射
const PYDANTIC_MSG_ZH: Record<string, string> = {
  email: "邮箱格式不正确",
  name: "联系人姓名不能为空",
  phone: "联系电话格式不正确",
  password: "密码不符合要求",
  company_name: "公司名称不能为空",
  registration_no: "注册号格式不正确",
  language_preference: "语言偏好选择无效",
  country_code: "国家/地区选择无效",
};

// 从 ApiError.data 中提取字段错误数组。
// 兼容两种后端格式:
//   1) 业务 409: { errors: [{ field, code, message }] }
//   2) Pydantic 422: { errors: [{ type, loc: ["body","email"], msg }] }
function extractFieldErrors(data: unknown): RegistrationFieldError[] | null {
  if (!data || typeof data !== "object") return null;
  const errs = (data as { errors?: unknown }).errors;
  if (!Array.isArray(errs) || errs.length === 0) return null;

  return errs.map((e: Record<string, unknown>) => {
    // 业务格式:已有 field + message
    if (typeof e.field === "string" && typeof e.message === "string") {
      return e as unknown as RegistrationFieldError;
    }
    // Pydantic 格式:从 loc 提取字段名,翻译为中文
    const loc = Array.isArray(e.loc) ? e.loc : [];
    const field = String(loc[loc.length - 1] || "unknown");
    const message = PYDANTIC_MSG_ZH[field] || "输入格式不正确";
    return { field, code: 42200, message } as RegistrationFieldError;
  });
}

export function StepForm({
  countryCode,
  languagePreference,
  draft,
  updateDraft,
  onBack,
  onSubmitted,
}: StepFormProps) {
  const country = getCountryByCode(countryCode);
  // password 不进 draft / sessionStorage,仅本组件 state
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<Partial<Record<FieldName, string | null>>>({});
  const [touched, setTouched] = useState<Partial<Record<FieldName, boolean>>>({});
  const [submitError, setSubmitError] = useState("");
  // v1.5 Δ3:后端返回的字段级错误(独立于客户端 errors,user 编辑该字段时清掉)
  const [fieldServerErrors, setFieldServerErrors] = useState<Partial<Record<FieldName, string>>>({});

  // PRD v1.4 Δ6:提交按钮置灰 - 全字段校验状态的实时映射。
  // useMemo 依赖 draft、密码、country.code,任一变化都重算。
  const fullForm = {
    ...draft,
    password,
    confirmPassword,
  };
  const validation = useMemo(
    () => validateAllRegisterFields(fullForm, countryCode),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      draft.company_name,
      draft.registration_no,
      draft.name,
      draft.phone,
      draft.email,
      password,
      confirmPassword,
      countryCode,
    ],
  );
  const isFormValid = validation.valid;
  const missingFields = validation.errors.map((e) => e.fieldLabel);

  if (!country) return null;

  const validateField = (
    f: FieldName,
    value: string,
    pwd?: string,
  ): string | null => {
    switch (f) {
      case "company_name":
        return validateRequired(value, "公司名称");
      case "registration_no":
        return validateRegistrationNoByCountry(countryCode, value);
      case "name":
        return validateRequired(value, "联系人姓名");
      case "phone":
        return validateSupplierPhone(value);
      case "email":
        return validateEmail(value, { required: "请填写邮箱", format: "邮箱格式不正确", domain: "邮箱域名不可用" });
      case "password":
        return validatePassword(value);
      case "confirmPassword":
        return validatePasswordConfirm(pwd ?? password, value);
    }
  };

  const setDraftField = (f: Exclude<FieldName, "password" | "confirmPassword">, raw: string) => {
    let v = raw;
    if (f === "registration_no" && country.regNo.transform) {
      v = country.regNo.transform(raw);
    }
    updateDraft({ [f]: v });
    if (errors[f]) setErrors((e) => ({ ...e, [f]: null }));
    // v1.5 Δ3:用户开始修改字段 → 清掉该字段的服务器错误
    if (fieldServerErrors[f]) {
      setFieldServerErrors((s) => {
        const next = { ...s };
        delete next[f];
        return next;
      });
    }
  };

  const blur = (f: FieldName) => {
    setTouched((t) => ({ ...t, [f]: true }));
    let val: string;
    if (f === "password") val = password;
    else if (f === "confirmPassword") val = confirmPassword;
    else val = draft[f as keyof typeof draft];
    setErrors((e) => ({ ...e, [f]: validateField(f, val) }));
  };

  // v1.5 Δ3:server 错误优先(已提交过、用户尚未修改),其次 touched 后的客户端错误
  const errOf = (f: FieldName): string | null =>
    fieldServerErrors[f] ?? (touched[f] ? errors[f] ?? null : null);

  const validateAll = (): string => {
    const fields: FieldName[] = [
      "company_name", "registration_no", "name", "phone", "email",
      "password", "confirmPassword",
    ];
    const newE: Partial<Record<FieldName, string | null>> = {};
    const newT: Partial<Record<FieldName, boolean>> = {};
    let first = "";
    for (const f of fields) {
      let val: string;
      if (f === "password") val = password;
      else if (f === "confirmPassword") val = confirmPassword;
      else val = draft[f as keyof typeof draft];
      const err = validateField(f, val);
      newE[f] = err;
      newT[f] = true;
      if (err && !first) first = err;
    }
    setErrors((e) => ({ ...e, ...newE }));
    setTouched((t) => ({ ...t, ...newT }));
    return first;
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const err = validateAll();
    if (err) {
      setSubmitError(err);
      return;
    }
    setSubmitError("");
    setFieldServerErrors({});
    setSubmitting(true);
    try {
      await authApi.registerSupplier({
        email: draft.email,
        name: draft.name,
        phone: draft.phone,
        password,
        company_name: draft.company_name,
        country_code: countryCode,
        registration_no: draft.registration_no,
        language_preference: languagePreference,
      });
      // 注册成功 → 只预填账号(/login 一次性消费),不落明文密码
      try {
        sessionStorage.setItem(
          "prefill_login",
          JSON.stringify({
            // WHY 用 email 不用 phone:SUPPLIER phone 走 i18n 占位校验(允许 +、空格、-),
            // 而 login _classify_identifier 仅识别纯 11 位中国手机号,prefill 国际格式 phone
            // 会被当 username 查必然 401。TODO(I18N-PHONE):各国 phone 精确规则就绪后再放开。
            identifier: draft.email,
          }),
        );
      } catch {
        // 隐私模式:降级到无自动填充
      }
      onSubmitted();
    } catch (e2) {
      // v1.5 Δ3:后端统一返回 data.errors 数组(单错误数组长度为 1);按字段定位 + 顶部 banner
      if (e2 instanceof ApiError) {
        const errs = extractFieldErrors(e2.data);
        if (errs) {
          const map: Partial<Record<FieldName, string>> = {};
          const knownFields: FieldName[] = [
            "company_name", "registration_no", "name", "phone", "email",
            "password", "confirmPassword",
          ];
          let hasUnknownField = false;
          for (const er of errs) {
            if (knownFields.includes(er.field as FieldName)) {
              map[er.field as FieldName] = er.message;
            } else {
              hasUnknownField = true;
            }
          }
          setFieldServerErrors(map);
          // 能定位到字段的错误只显示在字段下方,不在顶部重复;
          // 有无法定位的字段 或 多个错误时才显示顶部 banner
          if (hasUnknownField) {
            setSubmitError(errs.find((e) => !knownFields.includes(e.field as FieldName))?.message || "提交失败");
          } else if (errs.length > 1) {
            setSubmitError(multipleValidationBannerMessage(errs.length));
          } else {
            setSubmitError("");
          }
          // 滚动到首错字段
          setTimeout(() => {
            document.getElementById(errs[0].field)?.scrollIntoView({
              behavior: "smooth",
              block: "center",
            });
          }, 0);
        } else {
          setSubmitError(e2.message);
        }
      } else {
        setSubmitError("注册失败,请稍后重试");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={onSubmit} className="space-y-5" noValidate>
      <div>
        <h2 className="text-xl font-bold text-gray-900">海外供应商入驻</h2>
        <p className="mt-1 text-sm text-gray-500">请填写真实的自然人与企业组织信息</p>
      </div>

      {/* 当前国家与凭证规则提示(只读) */}
      <div className="flex items-center justify-between rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
        <div className="text-sm">
          <p className="text-gray-500">
            注册地:<span className="font-semibold text-gray-800">{country.nameZh}</span> · {country.nameEn}
          </p>
          <p className="mt-0.5 text-xs text-gray-400">
            凭证:{country.regNo.label} ({country.regNo.hint})
          </p>
        </div>
        <span className="rounded bg-[#003366] px-2 py-1 text-xs font-bold tracking-wide text-white">
          {country.code}
        </span>
      </div>

      {submitError && (
        <div className="flex items-center gap-2.5 rounded-lg border-l-4 border-red-500 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{submitError}</span>
        </div>
      )}

      <div className="space-y-1.5">
        <Label htmlFor="company_name" className="text-sm font-semibold text-gray-700">
          公司名称 *
        </Label>
        <input
          id="company_name" name="company_name" value={draft.company_name}
          onChange={(e) => setDraftField("company_name", e.target.value)}
          onBlur={() => blur("company_name")}
          placeholder="请填写完整公司名称"
          className={cls(errOf("company_name"))}
        />
        {errOf("company_name") && <p className="text-xs text-red-500">{errOf("company_name")}</p>}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="registration_no" className="flex items-center justify-between text-sm font-semibold text-gray-700">
          <span>
            {country.regNo.label} <span className="font-normal text-gray-400">({country.regNo.hint})</span> *
          </span>
          <span className="rounded bg-[#003366]/10 px-1.5 py-0.5 font-mono text-xs font-bold text-[#003366]">
            {country.code}
          </span>
        </Label>
        <input
          id="registration_no" name="registration_no" value={draft.registration_no}
          onChange={(e) => setDraftField("registration_no", e.target.value)}
          onBlur={() => blur("registration_no")}
          placeholder={country.regNo.label}
          className={cls(errOf("registration_no"))}
        />
        {errOf("registration_no") && <p className="text-xs text-red-500">{errOf("registration_no")}</p>}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="name" className="text-sm font-semibold text-gray-700">
            联系人 *
          </Label>
          <input
            id="name" name="name" value={draft.name}
            onChange={(e) => setDraftField("name", e.target.value)}
            onBlur={() => blur("name")}
            placeholder="您的姓名"
            className={cls(errOf("name"))}
          />
          {errOf("name") && <p className="text-xs text-red-500">{errOf("name")}</p>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="phone" className="text-sm font-semibold text-gray-700">
            联系电话 *
          </Label>
          <input
            id="phone" name="phone" value={draft.phone}
            onChange={(e) => setDraftField("phone", e.target.value)}
            onBlur={() => blur("phone")}
            placeholder="如 +60 12 345 6789"
            className={cls(errOf("phone"))}
          />
          {errOf("phone") && <p className="text-xs text-red-500">{errOf("phone")}</p>}
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="email" className="text-sm font-semibold text-gray-700">
          联系邮箱 *
        </Label>
        <input
          id="email" name="email" type="email" value={draft.email}
          autoComplete="email"
          onChange={(e) => setDraftField("email", e.target.value)}
          onBlur={() => blur("email")}
          placeholder="your@email.com"
          className={cls(errOf("email"))}
        />
        {errOf("email") && <p className="text-xs text-red-500">{errOf("email")}</p>}
      </div>

      {/* 密码 */}
      <div className="space-y-1.5">
        <Label htmlFor="password" className="text-sm font-semibold text-gray-700">
          输入密码 * <span className="font-normal text-gray-400">(11-50 位,需 3 类字符)</span>
        </Label>
        <div className="relative">
          <input
            id="password" name="password"
            type={showPwd ? "text" : "password"}
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (errors.password) setErrors((er) => ({ ...er, password: null }));
              if (errors.confirmPassword) setErrors((er) => ({ ...er, confirmPassword: null }));
            }}
            onBlur={() => blur("password")}
            autoComplete="new-password"
            placeholder="请输入密码"
            className={cls(errOf("password"), "pr-12")}
          />
          <button
            type="button" tabIndex={-1}
            onClick={() => setShowPwd((s) => !s)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            {showPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
        {errOf("password") && <p className="text-xs text-red-500">{errOf("password")}</p>}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="confirmPassword" className="text-sm font-semibold text-gray-700">
          密码确认 *
        </Label>
        <div className="relative">
          <input
            id="confirmPassword" name="confirmPassword"
            type={showConfirm ? "text" : "password"}
            value={confirmPassword}
            onChange={(e) => {
              setConfirmPassword(e.target.value);
              if (errors.confirmPassword) setErrors((er) => ({ ...er, confirmPassword: null }));
            }}
            onBlur={() => blur("confirmPassword")}
            autoComplete="new-password"
            placeholder="再次输入密码"
            className={cls(errOf("confirmPassword"), "pr-12")}
          />
          <button
            type="button" tabIndex={-1}
            onClick={() => setShowConfirm((s) => !s)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
        {errOf("confirmPassword") ? (
          <p className="mt-1 flex items-center gap-1 text-xs text-red-500">
            <AlertCircle className="h-3 w-3" /> {errOf("confirmPassword")}
          </p>
        ) : (
          confirmPassword &&
          password &&
          password === confirmPassword && (
            <p className="mt-1 flex items-center gap-1 text-xs text-[#10B981]">
              <CheckCircle2 className="h-3 w-3" /> 密码匹配
            </p>
          )
        )}
      </div>

      <div className="flex items-center gap-3 pt-2">
        <button
          type="button"
          onClick={onBack}
          className="h-12 flex-1 rounded-lg border border-gray-300 bg-white text-sm font-semibold text-gray-600 transition-colors hover:bg-gray-50"
        >
          ← 返回上一步
        </button>
        <button
          type="submit"
          disabled={!isFormValid || submitting}
          title={isFormValid ? "" : `请完善:${missingFields.join("、")}`}
          className={
            "flex h-12 flex-1 items-center justify-center gap-2 rounded-lg text-sm font-semibold shadow-sm transition-all active:scale-[0.99] " +
            (isFormValid && !submitting
              ? "bg-[#FF6B35] hover:bg-[#e05a25] text-white cursor-pointer"
              : "bg-gray-300 text-gray-500 cursor-not-allowed")
          }
        >
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" /> 提交中...
            </>
          ) : (
            "提交注册申请"
          )}
        </button>
      </div>
    </form>
  );
}
