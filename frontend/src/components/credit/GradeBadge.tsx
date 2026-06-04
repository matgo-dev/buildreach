"use client";
import type { Grade } from "@/lib/api/credit";

const META: Record<Grade, { bg: string; text: string; label: string; tagline: string }> = {
  A: { bg: "#d5e8d4", text: "#1e7f32", label: "A 级", tagline: "推荐合作" },
  B: { bg: "#fff2cc", text: "#9a7d00", label: "B 级", tagline: "可考虑合作" },
  C: { bg: "#ffe6cc", text: "#b25800", label: "C 级", tagline: "谨慎合作" },
  D: { bg: "#f8cecc", text: "#a8201a", label: "D 级", tagline: "不建议合作" },
};

export function GradeBadge({
  grade,
  size = "md",
  showTagline = false,
}: {
  grade: Grade | null | undefined;
  size?: "sm" | "md" | "lg";
  showTagline?: boolean;
}) {
  if (!grade) {
    return (
      <span className="inline-flex items-center rounded px-2 py-0.5 text-xs text-slate-400 bg-slate-100">
        无评分
      </span>
    );
  }
  const meta = META[grade];
  const sizeCls =
    size === "lg"
      ? "px-3 py-1.5 text-base font-bold"
      : size === "sm"
        ? "px-1.5 py-0.5 text-[10px] font-medium"
        : "px-2 py-0.5 text-xs font-semibold";
  return (
    <span className="inline-flex items-center gap-2">
      <span
        className={`inline-flex items-center rounded ${sizeCls}`}
        style={{ backgroundColor: meta.bg, color: meta.text }}
      >
        {meta.label}
      </span>
      {showTagline && (
        <span className="text-xs text-slate-500">{meta.tagline}</span>
      )}
    </span>
  );
}
