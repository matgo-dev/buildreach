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
    <div className="grid grid-cols-3 gap-2 rounded-xl border border-line bg-white p-3 sm:grid-cols-6 lg:grid-cols-9">
      <button
        type="button"
        onClick={() => onSelect("")}
        className={`h-8 w-full whitespace-nowrap rounded-full px-3.5 text-[13px] font-semibold transition-colors ${
          activeCode === ""
            ? "bg-lime text-teal-900"
            : "bg-teal-50 text-ink-2 hover:bg-teal-100 hover:text-teal-900"
        }`}
      >
        {allLabel}
      </button>
      {categories.map((c) => (
        <button
          key={c.code}
          type="button"
          onClick={() => onSelect(c.code)}
          className={`h-8 w-full whitespace-nowrap rounded-full px-3.5 text-[13px] font-semibold transition-colors ${
            activeCode === c.code
              ? "bg-lime text-teal-900"
              : "bg-teal-50 text-ink-2 hover:bg-teal-100 hover:text-teal-900"
          }`}
        >
          {c.name}
        </button>
      ))}
    </div>
  );
}
