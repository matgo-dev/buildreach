"use client";

import { useCallback, useRef } from "react";

type TransMetaStatus =
  | "src"
  | "auto"
  | "pending"
  | "failed"
  | "manual"
  | "stale";

interface LocalizedFieldEditorProps {
  /** Field name (e.g., "name", "description") */
  field: string;
  /** Label displayed above the field group */
  label: string;
  /** Current values per locale */
  values: Record<string, string>;
  /** trans_meta statuses per "field_locale" key (e.g., "name_en": "auto") */
  transMeta: Record<string, TransMetaStatus>;
  /** Source language of this record */
  sourceLang: string;
  /** Callback when any value changes: (locale, newValue) */
  onChange: (locale: string, value: string) => void;
  /** Use textarea instead of input */
  multiline?: boolean;
  /** Supported locales, defaults to ["zh", "en"] */
  locales?: string[];
  /** Whether field is required (source locale) */
  required?: boolean;
}

const LOCALE_LABELS: Record<string, string> = {
  zh: "中文",
  en: "English",
};

const STATUS_CONFIG: Record<
  TransMetaStatus,
  { label: string; className: string }
> = {
  src: {
    label: "原文",
    className: "bg-blue-100 text-blue-700",
  },
  auto: {
    label: "自动翻译",
    className: "bg-green-100 text-green-700",
  },
  pending: {
    label: "翻译中",
    className: "bg-yellow-100 text-yellow-700",
  },
  failed: {
    label: "翻译失败",
    className: "bg-red-100 text-red-700",
  },
  manual: {
    label: "已人工修改",
    className: "bg-purple-100 text-purple-700",
  },
  stale: {
    label: "待复核",
    className: "bg-orange-100 text-orange-700",
  },
};

/**
 * 多语言字段编辑器 —— 每个支持的 locale 一个输入框,附带翻译状态标签。
 * manual 状态仅在值实际发生变化时才设置(diff 原则)。
 */
export function LocalizedFieldEditor({
  field,
  label,
  values,
  transMeta,
  sourceLang,
  onChange,
  multiline = false,
  locales = ["zh", "en"],
  required = false,
}: LocalizedFieldEditorProps) {
  // 记录每个 locale 的初始值,用于 diff 判断是否真的修改过
  const initialValuesRef = useRef<Record<string, string>>({ ...values });

  const handleChange = useCallback(
    (locale: string, newValue: string) => {
      onChange(locale, newValue);
    },
    [onChange]
  );

  const handleBlur = useCallback(
    (locale: string) => {
      const initial = initialValuesRef.current[locale] ?? "";
      const current = values[locale] ?? "";
      // 源语言不需要标记 manual
      if (locale === sourceLang) return;
      // 只有值真正变化时才触发(由父组件决定是否更新 transMeta)
      // 这里通过 onChange 传递信号,父组件可根据 diff 设置 manual
      if (current !== initial) {
        // 值确实变了,父组件应将 transMeta 设为 manual
        onChange(locale, current);
      }
    },
    [values, sourceLang, onChange]
  );

  return (
    <div className="space-y-3">
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      {locales.map((locale) => {
        const metaKey = `${field}_${locale}`;
        const isSource = locale === sourceLang;
        const status: TransMetaStatus = isSource
          ? "src"
          : transMeta[metaKey] ?? "pending";
        const { label: statusLabel, className: badgeClass } =
          STATUS_CONFIG[status];
        const value = values[locale] ?? "";
        const inputId = `${field}-${locale}`;

        const sharedProps = {
          id: inputId,
          value,
          onChange: (
            e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
          ) => handleChange(locale, e.target.value),
          onBlur: () => handleBlur(locale),
          placeholder: `${LOCALE_LABELS[locale] ?? locale}...`,
          required: isSource && required,
          className:
            "block w-full rounded-md border border-gray-300 px-3 py-2 text-sm " +
            "shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 " +
            "disabled:bg-gray-50 disabled:text-gray-500",
        };

        return (
          <div key={locale} className="flex items-start gap-2">
            {/* locale 标签 + 状态 badge */}
            <div className="flex w-24 shrink-0 flex-col items-start gap-1 pt-2">
              <span className="text-xs font-medium text-gray-500 uppercase">
                {LOCALE_LABELS[locale] ?? locale}
              </span>
              <span
                className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium ${badgeClass}`}
              >
                {statusLabel}
              </span>
            </div>

            {/* 输入框 */}
            <div className="flex-1">
              {multiline ? (
                <textarea rows={3} {...sharedProps} />
              ) : (
                <input type="text" {...sharedProps} />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
