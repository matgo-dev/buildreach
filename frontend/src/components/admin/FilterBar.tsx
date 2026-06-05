"use client";

import { Search } from "lucide-react";

interface FilterBarProps {
  keyword: string;
  onKeywordChange: (v: string) => void;
  searchPlaceholder?: string;
  children?: React.ReactNode; // 额外的筛选器 slot
}

/**
 * 运营后台通用筛选条。
 * 对标截图：搜索框 + 可扩展的下拉筛选器。
 */
export function FilterBar({ keyword, onKeywordChange, searchPlaceholder, children }: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3">
      <div className="relative flex-1 max-w-sm">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          placeholder={searchPlaceholder ?? "搜索..."}
          className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-10 pr-4 text-[13px] text-slate-700 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          value={keyword}
          onChange={(e) => onKeywordChange(e.target.value)}
        />
      </div>
      {children}
    </div>
  );
}

/** 运营后台通用筛选下拉框。 */
export function FilterSelect({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <select
      className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-[13px] text-slate-700 focus:border-blue-500 focus:outline-none"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );
}
