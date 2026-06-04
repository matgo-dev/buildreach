// 供应商 3 步向导 · 9 国凭证规则配置(PRD v1.3 §3 / §5.3)。
//
// 边界:仅"前后端必须对齐 / 错一字即 bug"的字符串放这里。一次性展示文案直接写在
// 组件 JSX。Step 标题、副标题、字段 label、placeholder、按钮文案、Dashboard banner
// 全部硬编码在使用处。
//
// 后端对应:backend/app/constants/country_registration.py(逐字一致,手工同步)。

/** 9 国凭证规则的单条配置 */
export interface CountryRule {
  /** ISO 2 字母国家码,与后端 COUNTRY_CODES 一一对应 */
  code: CountryCode;
  nameZh: string;
  nameEn: string;
  /** 本国主语言 ISO 639-1 code（拼接 BCP 47 tag 用,如 "ar" + "-MA" → "ar-MA"） */
  localLang: string;
  /** 本国主语言显示名(本地语写法) */
  localLangName: string;
  regNo: {
    /** 凭证名(显示在 Step 3 字段 label),如 "SSM 注册号" */
    label: string;
    /** 凭证规则提示,如 "12 位纯数字" */
    hint: string;
    /** 占位正则(TODO(REG-RULE) 精确规则待补) */
    regex: RegExp;
    /** 输入规整函数(如 CN 自动转大写+截 18 位、纯数字国家剔除非数字) */
    transform?: (v: string) => string;
  };
}

export const COUNTRIES = [
  {
    code: "CN",
    nameZh: "中国",
    nameEn: "China",
    localLang: "zh",
    localLangName: "中文",
    regNo: {
      label: "统一社会信用代码",
      hint: "18 位",
      // TODO(REG-RULE):国标 GB 32100-2015 校验位算法待补,本轮只验长度+字符集
      regex: /^[0-9A-Z]{18}$/,
      // 字母数字国(PRD v1.4 Δ5):trim + toUpperCase + slice
      transform: (v: string) => v.trim().toUpperCase().slice(0, 18),
    },
  },
  {
    code: "KH",
    nameZh: "柬埔寨",
    nameEn: "Cambodia",
    localLang: "km",
    localLangName: "ខ្មែរ",
    regNo: {
      label: "MOC 注册号",
      hint: "6-12 位数字",
      // 柬埔寨 MOC 注册号为纯数字,与后端 country_registration.py 的正则对齐
      regex: /^[0-9]{6,12}$/,
      transform: (v: string) => v.replace(/[^0-9]/g, "").slice(0, 12),
    },
  },
  {
    code: "PK",
    nameZh: "巴基斯坦",
    nameEn: "Pakistan",
    localLang: "ur",
    localLangName: "اُردُو",
    regNo: {
      // PRD v1.4 Δ3:NTN → SECP
      label: "SECP 注册号",
      hint: "7-10 位字母数字",
      // TODO(REG-RULE):PRD v1.4 PM 文档基准
      regex: /^[A-Z0-9]{7,10}$/,
      transform: (v: string) => v.trim().toUpperCase().slice(0, 10),
    },
  },
  {
    code: "MA",
    nameZh: "摩洛哥",
    nameEn: "Morocco",
    localLang: "ar",
    localLangName: "العربية",
    regNo: {
      // PRD v1.4 Δ3:RC → ICE
      label: "ICE 企业统一编号",
      hint: "15 位数字",
      // TODO(REG-RULE):PRD v1.4 PM 文档基准
      regex: /^[0-9]{15}$/,
      transform: (v: string) => v.trim().replace(/\D/g, "").slice(0, 15),
    },
  },
  {
    code: "IQ",
    nameZh: "伊拉克",
    nameEn: "Iraq",
    localLang: "ar",
    localLangName: "العربية",
    regNo: {
      label: "MoC 商业登记号",
      hint: "6-10 位数字",
      // TODO(REG-RULE):PRD v1.4 PM 文档基准
      regex: /^[0-9]{6,10}$/,
      transform: (v: string) => v.trim().replace(/\D/g, "").slice(0, 10),
    },
  },
  {
    code: "ID",
    nameZh: "印尼",
    nameEn: "Indonesia",
    localLang: "id",
    localLangName: "Bahasa Indonesia",
    regNo: {
      label: "NIB(营业识别号)",
      hint: "13 位纯数字",
      regex: /^[0-9]{13}$/,
      // 纯数字国(PRD v1.4 Δ5):trim + replace(/\D/g) + slice
      transform: (v: string) => v.trim().replace(/\D/g, "").slice(0, 13),
    },
  },
  {
    code: "MY",
    nameZh: "马来西亚",
    nameEn: "Malaysia",
    localLang: "ms",
    localLangName: "Bahasa Melayu",
    regNo: {
      label: "SSM 注册号",
      hint: "12 位纯数字",
      regex: /^[0-9]{12}$/,
      transform: (v: string) => v.trim().replace(/\D/g, "").slice(0, 12),
    },
  },
  {
    code: "SA",
    nameZh: "沙特阿拉伯",
    nameEn: "Saudi Arabia",
    localLang: "ar",
    localLangName: "العربية",
    regNo: {
      label: "CR 商业登记号",
      hint: "10 位数字",
      regex: /^[0-9]{10}$/,
      transform: (v: string) => v.trim().replace(/\D/g, "").slice(0, 10),
    },
  },
  {
    code: "AE",
    nameZh: "阿联酋",
    nameEn: "UAE",
    localLang: "ar",
    localLangName: "العربية",
    regNo: {
      label: "Trade License No",
      hint: "6-12 位字母数字",
      // TODO(REG-RULE):PRD v1.4 PM 文档基准
      regex: /^[A-Z0-9]{6,12}$/,
      transform: (v: string) => v.trim().toUpperCase().slice(0, 12),
    },
  },
] as const satisfies readonly CountryRule[];

export type CountryCode =
  | "CN" | "KH" | "PK" | "MA" | "IQ" | "ID" | "MY" | "SA" | "AE";

/** language_preference 合法值:BCP 47 locale tag 封闭白名单(10 个)。与后端 LANGUAGE_CODES 必须逐字一致 */
export const LANGUAGE_CODES = ["zh-CN", "en", "km-KH", "ur-PK", "ar-MA", "ar-IQ", "ar-SA", "ar-AE", "id-ID", "ms-MY"] as const;
export type LanguageCode = typeof LANGUAGE_CODES[number];

/** 重复注册错误文案:前后端逐字一致(后端 constants 中同名常量),不暴露任何 owner 信息 */
export const DUPLICATE_REGISTRATION_ERROR_MESSAGE =
  "当前企业已在平台注册。如需加入,请联系您所在企业的平台管理员添加账号。";

/**
 * 重复入驻业务错误码(PRD v1.4 Δ9):数字 40901。
 * 前端识别错误必须用数字 `if (response.code === BUSINESS_CODE_DUPLICATE_SUPPLIER_REGISTRATION)`,
 * **严禁** 与字符串比较(异常类名 `SupplierAlreadyRegisteredError` 只在后端 Python 侧可见)。
 */
export const BUSINESS_CODE_DUPLICATE_SUPPLIER_REGISTRATION = 40901;

/** v1.5 Δ2:邮箱已注册业务码(数字 40902)。前后端逐字一致。 */
export const BUSINESS_CODE_EMAIL_ALREADY_REGISTERED = 40902;
/** v1.5 Δ2:手机号已注册业务码(数字 40903)。前后端逐字一致。 */
export const BUSINESS_CODE_PHONE_ALREADY_REGISTERED = 40903;

export const EMAIL_ALREADY_REGISTERED_MESSAGE = "该邮箱已注册,请直接登录或更换邮箱";
export const PHONE_ALREADY_REGISTERED_MESSAGE = "该手机号已注册,请直接登录或更换手机号";

/** v1.5 Δ3:多错误并发时顶部 banner 模板;单错误不使用此文案 */
export function multipleValidationBannerMessage(n: number): string {
  return `请修正以下 ${n} 项问题`;
}

/** v1.5 Δ3:后端 data.errors 数组中单条错误的形状(前后端逐字一致) */
export interface RegistrationFieldError {
  field: string;
  code: number;
  message: string;
}

/** SupplierOrg 状态字符串(未来增 status 时统一加在此处) */
export const STATUS_DRAFT = "DRAFT";

/** sessionStorage 草稿 key(PRD v1.3 §2.3) */
export const DRAFT_STORAGE_KEY = "register_supplier_draft";

/** Step 1 选中国家后的浅蓝信息条文案(数据驱动) */
export function countryHintTemplate(c: CountryRule): string {
  return `您选择了 ${c.nameZh}。后续系统将要求您提供 ${c.regNo.label}(${c.regNo.hint})作为核心准入凭证。`;
}

/** O(1) 查表:code → 配置 */
export function getCountryByCode(code: string): CountryRule | undefined {
  return COUNTRIES.find((c) => c.code === code);
}
