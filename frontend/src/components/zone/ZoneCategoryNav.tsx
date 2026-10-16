"use client";

import type { ZoneCategory } from "@/lib/api/zones";

interface Props {
  categories: ZoneCategory[];
  activeCode: string;
  allLabel: string;
  /** 行标签(如「应用场景」「商品大类」):两条轴并排时用户靠它分清,读屏也靠它(role=group) */
  label: string;
  onSelect: (code: string) => void;
}

const CHIP = "h-8 whitespace-nowrap rounded-full px-3.5 text-[13px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600";
const ON = "bg-lime text-teal-900";
const OFF = "bg-teal-50 text-ink-2 hover:bg-teal-100 hover:text-teal-900";

/**
 * 专区筛选行(一条轴一行)。chip 按内容宽度自动换行,不用固定列网格——
 * 矿业大类名(「工程机械与车辆易损件」)比格子宽,固定列会把字裁掉叠到隔壁。
 */
export function ZoneCategoryNav({ categories, activeCode, allLabel, label, onSelect }: Props) {
  return (
    <div
      role="group"
      aria-label={label}
      className="flex flex-col gap-2 rounded-xl border border-line bg-white p-3 sm:flex-row sm:items-start"
    >
      <span className="shrink-0 pt-1.5 text-[13px] font-semibold text-muted sm:w-20">{label}</span>
      <div className="flex flex-wrap gap-2">
        <button type="button" aria-pressed={activeCode === ""} onClick={() => onSelect("")} className={`${CHIP} ${activeCode === "" ? ON : OFF}`}>
          {allLabel}
        </button>
        {categories.map((c) => (
          <button
            key={c.code}
            type="button"
            aria-pressed={activeCode === c.code}
            onClick={() => onSelect(c.code)}
            className={`${CHIP} ${activeCode === c.code ? ON : OFF}`}
          >
            {c.name}
          </button>
        ))}
      </div>
    </div>
  );
}
