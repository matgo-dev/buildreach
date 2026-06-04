"use client";

// 3 步向导 Step 2:语言偏好。
// 三个按钮 + 底部「← 返回上一步」/「下一步」。颜色用项目深蓝/橙(不用截图渐变紫)。
// 本轮只存 language_preference,**不真翻译**(T-I18N)。
//
// 设计:点语言按钮 = 选择(不自动推进)→ 用底部「下一步」显式推进。
// 这样从 Step 3 回 Step 2 时,选中态保留,用户能直接「下一步」继续。

import { ChevronRight, Globe } from "lucide-react";

import {
  getCountryByCode,
  type CountryCode,
  type LanguageCode,
} from "@/config/country-registration-rules";

interface StepLanguageProps {
  countryCode: CountryCode;
  selected: LanguageCode | "";
  onSelect: (lang: LanguageCode) => void;
  onBack: () => void;
  onNext: () => void;
}

export function StepLanguage({ countryCode, selected, onSelect, onBack, onNext }: StepLanguageProps) {
  const country = getCountryByCode(countryCode);
  if (!country) return null;

  // BCP 47 locale tag:本地语 = localLang-countryCode, English = en, 中文 = zh-CN
  const localTag = `${country.localLang}-${country.code}` as LanguageCode;
  const options: { lang: LanguageCode; title: string; subtitle: string }[] = [
    {
      lang: localTag,
      title: `翻译为 ${country.localLangName}`,
      subtitle: localTag,
    },
    { lang: "en", title: "翻译为 English", subtitle: "en" },
    { lang: "zh-CN", title: "保持中文", subtitle: "zh-CN" },
  ];

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-bold text-gray-900">是否开启多语种适配?</h2>
        {/* [待评审] 文案对齐「只记录不翻译」口径 */}
        <p className="mt-1 text-sm text-gray-500">
          我们会记录您的语言偏好,用于后续多语种适配;本轮仅记录,不改变当前页面语言。
        </p>
      </div>

      <div className="space-y-3">
        {options.map((opt) => {
          const active = selected === opt.lang;
          return (
            <button
              key={opt.lang + opt.title}
              type="button"
              onClick={() => onSelect(opt.lang)}
              className={
                "flex w-full items-center gap-3 rounded-xl border-2 px-4 py-3 text-left transition-all " +
                (active
                  ? "border-[#FF6B35] bg-[#FF6B35]/5"
                  : "border-gray-200 hover:border-[#003366] hover:bg-[#003366]/5")
              }
            >
              <div
                className={
                  "flex h-10 w-10 items-center justify-center rounded-lg " +
                  (active ? "bg-[#FF6B35]/15" : "bg-gray-50")
                }
              >
                <Globe className={"h-5 w-5 " + (active ? "text-[#FF6B35]" : "text-[#003366]")} />
              </div>
              <div className="flex-1">
                <p
                  className={
                    "text-sm font-semibold " + (active ? "text-[#FF6B35]" : "text-gray-800")
                  }
                >
                  {opt.title}
                </p>
                <p className="text-xs text-gray-400">{opt.subtitle}</p>
              </div>
            </button>
          );
        })}
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
          type="button"
          onClick={onNext}
          disabled={!selected}
          className="flex h-12 flex-1 items-center justify-center gap-2 rounded-lg bg-[#FF6B35] text-sm font-semibold text-white shadow-sm transition-all hover:bg-[#e05a25] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-50"
        >
          下一步 <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
