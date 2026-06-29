// 集中前端字段校验规则。后端规则在 schemas/auth.py 与 schemas/me.py。
// 返回 null = 通过;返回字符串 = 错误文案。

import { getCountryByCode } from "@/config/country-registration-rules";

export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
// 后端 email-validator 拒绝的保留/特殊 TLD,前端同步拦截
const RESERVED_EMAIL_TLDS = /\.(local|test|example|invalid|localhost|internal|corp|home|lan)$/i;
// 中国大陆手机号严格规则(BUYER 注册仍用)
export const PHONE_RE = /^1[3-9]\d{9}$/;
// SUPPLIER 注册占位规则:6-20 位,允许 +、数字、空格、短横(覆盖各国常见格式)
// TODO(I18N-PHONE):各国 phone 精确规则待补,本轮宽校验
export const SUPPLIER_PHONE_RE = /^[+0-9\s\-]{6,20}$/;
// 与后端 USERNAME_REGEX 等价:3-50 位字母/数字/下划线/短横,不能纯数字
export const USERNAME_RE = /^(?![0-9]+$)[A-Za-z0-9_\-]{3,50}$/;
// 18 位大写字母 + 数字(国标 GB 32100-2015)
export const USC_RE = /^[0-9A-Z]{18}$/;
// 与后端 validate_password_strength 等价:6-20 位,仅字母和数字(对齐阿里国际站)
export const PASSWORD_MIN_LENGTH = 6;
export const PASSWORD_MAX_LENGTH = 20;
export const PASSWORD_RE = /^[A-Za-z0-9]{6,20}$/;
// 错误文案与后端 PASSWORD_RULE_MESSAGE 逐字一致
export const PASSWORD_RULE_MESSAGE = "密码须 6-20 位,仅限字母和数字";

export interface EmailMessages {
  required: string;
  format: string;
  domain: string;
}

export function validateEmail(v: string, msgs: EmailMessages): string | null {
  if (!v) return msgs.required;
  if (!EMAIL_RE.test(v)) return msgs.format;
  const domain = v.split("@")[1] || "";
  if (RESERVED_EMAIL_TLDS.test(domain)) return msgs.domain;
  return null;
}

/** 选填手机号:留空通过;若提供则校验格式。 */
export function validatePhoneOptional(v: string): string | null {
  if (!v) return null;
  if (!PHONE_RE.test(v)) return "手机号须为 11 位中国大陆号码(1 开头,第二位 3-9)";
  return null;
}

/** 必填手机号。 */
export function validatePhoneRequired(v: string): string | null {
  if (!v) return "请填写手机号";
  return validatePhoneOptional(v);
}

/** 选填用户名:留空通过;若提供则校验格式。 */
export function validateUsernameOptional(v: string): string | null {
  if (!v) return null;
  if (!USERNAME_RE.test(v))
    return "用户名 3-50 位,只能含字母/数字/下划线/短横,且不能纯数字";
  return null;
}

export function validateUsc(v: string): string | null {
  if (!v) return "请填写统一社会信用代码";
  if (!USC_RE.test(v)) return "统一社会信用代码须为 18 位大写字母与数字";
  return null;
}

export function validatePassword(v: string): string | null {
  if (!v) return "请填写密码";
  if (!PASSWORD_RE.test(v)) return PASSWORD_RULE_MESSAGE;
  return null;
}

export function validatePasswordConfirm(pwd: string, confirm: string): string | null {
  if (!confirm) return "请再次输入密码";
  if (pwd !== confirm) return "两次密码不一致";
  return null;
}

export function validateRequired(v: string, label = "此项"): string | null {
  if (!v.trim()) return `${label}不能为空`;
  return null;
}

/**
 * BUYER 注册手机号/WhatsApp:只校验非空,不限制格式。
 * 东非用户号码格式多样,后端统一 E.164 归一化。
 */
export function validatePhone(v: string): boolean {
  return v.trim().length > 0;
}

export function validateWhatsApp(v: string): boolean {
  return v.trim().length > 0;
}

/** SUPPLIER 注册手机号:占位规则,TODO(I18N-PHONE)各国精确规则待补。 */
export function validateSupplierPhone(v: string): string | null {
  if (!v) return "请填写联系电话";
  if (!SUPPLIER_PHONE_RE.test(v))
    return "联系电话格式不正确(6-20 位,允许 +、数字、空格、短横)";
  return null;
}

/** 按国家分发凭证号校验:用 `country-registration-rules.ts` 的占位 regex。TODO(REG-RULE) 各国精确规则待补。 */
export function validateRegistrationNoByCountry(
  countryCode: string,
  value: string,
): string | null {
  if (!value) return "请填写注册号";
  const country = getCountryByCode(countryCode);
  if (!country) return "请先选择国家";
  if (!country.regNo.regex.test(value))
    return `${country.regNo.label}格式不正确(${country.regNo.hint})`;
  return null;
}

// ===== PRD v1.4 Δ6:提交按钮置灰 - 主流程级硬规则 =====

/** Step 3 表单全字段输入(密码因不进 sessionStorage,从组件 state 临时合入) */
export interface SupplierRegisterFullForm {
  company_name: string;
  registration_no: string;
  name: string;
  phone: string;
  email: string;
  password: string;
  confirmPassword: string;
}

export interface FieldError {
  field: keyof SupplierRegisterFullForm;
  fieldLabel: string;
  message: string;
}

/**
 * Step 3 全字段校验。`isFormValid` = `errors.length === 0`。
 * 用于:1) 提交按钮 disabled 绑定;2) hover title 拼接 `请完善:X、Y、Z`。
 *
 * 入参 countryCode 用于按国家分发 registration_no 正则;空字符串时 registration_no 报"请先选择国家"。
 */
export function validateAllRegisterFields(
  form: SupplierRegisterFullForm,
  countryCode: string,
): { valid: boolean; errors: FieldError[] } {
  const errors: FieldError[] = [];

  const push = (
    field: keyof SupplierRegisterFullForm,
    fieldLabel: string,
    message: string | null,
  ) => {
    if (message) errors.push({ field, fieldLabel, message });
  };

  push("company_name", "公司名称", validateRequired(form.company_name, "公司名称"));
  push(
    "registration_no",
    "注册号",
    validateRegistrationNoByCountry(countryCode, form.registration_no),
  );
  push("name", "联系人", validateRequired(form.name, "联系人姓名"));
  push("phone", "联系电话", validateSupplierPhone(form.phone));
  push("email", "联系邮箱", validateEmail(form.email, {
    required: "请填写邮箱",
    format: "邮箱格式不正确",
    domain: "邮箱域名不可用,请使用正式邮箱地址(如 .com、.cn)",
  }));
  push("password", "密码", validatePassword(form.password));
  push(
    "confirmPassword",
    "密码确认",
    validatePasswordConfirm(form.password, form.confirmPassword),
  );

  return { valid: errors.length === 0, errors };
}
