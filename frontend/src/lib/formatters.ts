/**
 * Locale-aware formatting utilities.
 *
 * Conventions:
 * - Monetary amounts are stored as numeric value + ISO 4217 currency code (e.g., 1500.00 + "USD").
 *   Currency is a BUSINESS attribute, not a locale attribute. No FX conversion here.
 * - Timestamps are stored as UTC ISO 8601 strings from the API.
 *   Display converts to user's local timezone. No timezone storage on client.
 * - Formatting is locale-dependent (thousand separators, decimal style, date order)
 *   but NEVER involves value conversion (no FX rates, no timezone persistence).
 *
 * Suggested replacement points in existing code:
 * - Any hardcoded toLocaleString() calls in table columns
 * - Any manual date formatting with string slicing
 * - Any `new Date().toLocaleDateString()` without explicit locale
 */

/**
 * Format a number according to the given locale.
 * Pure Intl wrapper - no business logic.
 */
export function formatNumber(
  value: number,
  locale: string,
  options?: Intl.NumberFormatOptions
): string {
  return new Intl.NumberFormat(locale, options).format(value);
}

/**
 * Format a monetary amount with currency symbol.
 * IMPORTANT: Currency is a business data attribute, NOT a locale attribute.
 * This function NEVER does currency conversion - it only formats the display.
 *
 * @param amount   - The raw numeric amount
 * @param currency - ISO 4217 currency code (e.g., "USD", "TZS", "CNY")
 * @param locale   - Display locale (only affects formatting: thousand separators, decimal style)
 */
export function formatCurrency(
  amount: number,
  currency: string,
  locale: string,
  options?: Intl.NumberFormatOptions
): string {
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    ...options,
  }).format(amount);
}

/**
 * Format a date/datetime for display.
 * Input should be ISO 8601 / UTC timestamp from the API.
 * Converts to user's local timezone for display.
 */
export function formatDate(
  isoString: string,
  locale: string,
  options?: Intl.DateTimeFormatOptions
): string {
  // 后端存 UTC naive datetime（无时区后缀），追加 Z 让浏览器按 UTC 解析后自动转本地时区
  const normalized = /[Z+\-]\d{0,2}:?\d{0,2}$/.test(isoString) ? isoString : isoString + "Z";
  const date = new Date(normalized);
  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    ...options,
  }).format(date);
}

/**
 * Format a date as relative time (e.g., "3 days ago", "3 天前").
 * Uses Intl.RelativeTimeFormat with automatic unit selection.
 */
export function formatRelativeTime(
  isoString: string,
  locale: string
): string {
  const normalized = /[Z+\-]\d{0,2}:?\d{0,2}$/.test(isoString) ? isoString : isoString + "Z";
  const date = new Date(normalized);
  const now = Date.now();
  const diffMs = date.getTime() - now;
  const absDiffMs = Math.abs(diffMs);

  // 选择合适的时间单位
  const units: { unit: Intl.RelativeTimeFormatUnit; ms: number }[] = [
    { unit: "year", ms: 365.25 * 24 * 60 * 60 * 1000 },
    { unit: "month", ms: 30.44 * 24 * 60 * 60 * 1000 },
    { unit: "week", ms: 7 * 24 * 60 * 60 * 1000 },
    { unit: "day", ms: 24 * 60 * 60 * 1000 },
    { unit: "hour", ms: 60 * 60 * 1000 },
    { unit: "minute", ms: 60 * 1000 },
  ];

  for (const { unit, ms } of units) {
    if (absDiffMs >= ms) {
      const value = Math.round(diffMs / ms);
      return new Intl.RelativeTimeFormat(locale, { numeric: "auto" }).format(
        value,
        unit
      );
    }
  }

  // < 1 minute
  return new Intl.RelativeTimeFormat(locale, { numeric: "auto" }).format(
    0,
    "second"
  );
}

/**
 * 按 locale 选取多语言字段值。
 *
 * 后端返回 _zh/_en 分列 + get_localized() 合成的本地化字段(含 sw 等)。
 * zh → 优先 zhVal; en → 优先 enVal; 其他语言 → 优先 fallback(后端已本地化的值)。
 *
 * @param locale  当前 locale ("zh" | "en" | "sw" | ...)
 * @param zhVal   _zh 列值
 * @param enVal   _en 列值
 * @param fallback 后端 get_localized() 返回的已本地化值
 */
export function localizedField(
  locale: string,
  zhVal: string | null | undefined,
  enVal: string | null | undefined,
  fallback?: string | null | undefined,
): string {
  if (locale === "zh") return zhVal || fallback || enVal || "";
  if (locale === "en") return enVal || fallback || zhVal || "";
  return fallback || enVal || zhVal || "";
}
