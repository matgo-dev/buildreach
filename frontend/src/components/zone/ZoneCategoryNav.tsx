"use client";

import type { ZoneCategory } from "@/lib/api/zones";

interface Props {
  categories: ZoneCategory[];
  activeCode: string;
  allLabel: string;
  onSelect: (code: string) => void;
}

/**
 * 专区大类导航(客户视角) — 与商城 FilterBar 的分类 chip 风格一致。
 */
export function ZoneCategoryNav({ categories, activeCode, allLabel, onSelect }: Props) {
  return (
    <div className="flex flex-wrap gap-2 rounded-xl border border-line bg-white p-3">
      <button
        type="button"
        onClick={() => onSelect("")}
        className={`h-8 shrink-0 rounded-full px-3.5 text-[13px] font-semibold transition-colors ${
          activeCode === ""
            ? "bg-teal-800 text-white"
            : "bg-gray-100 text-gray-600 hover:bg-teal-50 hover:text-teal-800"
        }`}
      >
        {allLabel}
      </button>
      {categories.map((c) => (
        <button
          key={c.code}
          type="button"
          onClick={() => onSelect(c.code)}
          className={`h-8 shrink-0 rounded-full px-3.5 text-[13px] font-semibold transition-colors ${
            activeCode === c.code
              ? "bg-teal-800 text-white"
              : "bg-gray-100 text-gray-600 hover:bg-teal-50 hover:text-teal-800"
          }`}
        >
          {c.name}
        </button>
      ))}
    </div>
  );
}
