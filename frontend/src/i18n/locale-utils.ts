import { routing } from "./routing";

/**
 * 将 BCP 47 language_preference 映射到 next-intl 支持的 locale
 * "zh-CN" → "zh", "en" → "en", "km-KH" → "en"(非中文一律 fallback 到 en)
 * null → "zh"(采购方/管理员/运营默认中文)
 */
export function preferenceToLocale(pref: string | null | undefined): string {
  if (!pref) return "zh";
  // 中文系(zh / zh-CN / zh-TW 等)
  if (pref.startsWith("zh")) return "zh";
  // 当前支持的 locale 直接匹配
  const base = pref.split("-")[0];
  if (routing.locales.includes(base as (typeof routing.locales)[number])) return base;
  // 其他语言 fallback 到 en
  return "en";
}
