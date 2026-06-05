// TODO: 后端 backend/app/i18n/locale_utils.py 中的 normalize_locale 使用相同规则,两端必须保持同步

/**
 * Explicit BCP 47 → locale mapping. Add entries for new locales.
 * Reserved: zh-tw/zh-hk/zh-hant for future Traditional Chinese.
 */
const LOCALE_MAP: Record<string, string> = {
  zh: "zh",
  "zh-cn": "zh",
  "zh-tw": "zh", // Reserved for future zh-hant support
  "zh-hk": "zh", // Reserved
  "zh-hant": "zh", // Reserved
  en: "en",
  "en-us": "en",
  "en-gb": "en",
  "en-au": "en",
};

/**
 * Normalize a BCP 47 language preference string to a supported next-intl locale.
 *
 * Resolution order:
 * 1. null/empty → "zh" (default for domestic users)
 * 2. Exact match in LOCALE_MAP
 * 3. Base language code match (e.g., "en-nz" → "en")
 * 4. Unsupported → "en" (international fallback)
 */
export function normalizeLocale(raw: string | null | undefined): string {
  if (!raw) return "zh";
  const key = raw.trim().toLowerCase();
  if (key in LOCALE_MAP) return LOCALE_MAP[key];
  // 尝试基础语言码
  const base = key.includes("-") ? key.split("-")[0] : key;
  if (base in LOCALE_MAP) return LOCALE_MAP[base];
  // 不认识的语言大概率是外国用户，回退到 en 比 zh 更合理
  return "en";
}

/** @deprecated Use normalizeLocale instead. Kept for backwards compatibility. */
export const preferenceToLocale = normalizeLocale;
