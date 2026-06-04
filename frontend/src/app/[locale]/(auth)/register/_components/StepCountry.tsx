"use client";

// 3 步向导 Step 1:选择企业注册地。
// 文案严格按 PRD v1.3 §5.3,不进配置文件(一次性展示)。

import { ChevronRight } from "lucide-react";

import {
  COUNTRIES,
  countryHintTemplate,
  getCountryByCode,
  type CountryCode,
} from "@/config/country-registration-rules";

interface StepCountryProps {
  selected: CountryCode | "";
  onSelect: (code: CountryCode) => void;
  onNext: () => void;
}

export function StepCountry({ selected, onSelect, onNext }: StepCountryProps) {
  const country = selected ? getCountryByCode(selected) : undefined;

  // PRD v1.4 Δ4:重新选择国家时,父级 onSelect 内自动清 registration_no
  // 和重置 language_preference(由 SupplierWizard 实现)
  const handleChange = (code: CountryCode) => {
    if (code !== selected) onSelect(code);
  };

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-bold text-gray-900">选择您的企业注册地</h2>
        <p className="mt-1 text-sm text-gray-500">
          请严格按照营业执照所在国家选择,这决定了后续的资质校验标准。
        </p>
      </div>

      <div className="space-y-1.5">
        <label htmlFor="country-select" className="text-sm font-semibold text-gray-700">
          企业注册地 <span className="text-red-500">*</span>
        </label>
        <select
          id="country-select"
          value={selected}
          onChange={(e) => handleChange(e.target.value as CountryCode)}
          className="h-11 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-800 transition-all focus:border-[#003366] focus:outline-none focus:ring-2 focus:ring-[#003366]/15"
        >
          <option value="" disabled>
            请选择国家 / 地区
          </option>
          {COUNTRIES.map((c) => (
            <option key={c.code} value={c.code}>
              {c.nameZh} · {c.nameEn} ({c.code})
            </option>
          ))}
        </select>
      </div>

      {country && (
        <div className="rounded-lg border-l-4 border-[#003366] bg-[#003366]/5 px-4 py-3 text-sm text-[#003366]">
          {countryHintTemplate(country)}
        </div>
      )}

      <button
        type="button"
        onClick={onNext}
        disabled={!selected}
        className="mt-2 flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-[#FF6B35] text-base font-semibold text-white shadow-sm transition-all hover:bg-[#e05a25] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-50"
      >
        下一步 <ChevronRight className="h-4 w-4" />
      </button>
    </div>
  );
}
