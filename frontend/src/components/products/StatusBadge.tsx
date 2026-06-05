"use client";

const STATUS_MAP: Record<string, { label: string; cls: string }> = {
  ACTIVE: { label: "已上架", cls: "bg-emerald-100 text-emerald-700" },
  DRAFT: { label: "草稿", cls: "bg-slate-100 text-slate-600" },
  INACTIVE: { label: "已下架", cls: "bg-red-100 text-red-600" },
};

export function StatusBadge({ status }: { status: string }) {
  const s = STATUS_MAP[status] ?? { label: status, cls: "bg-gray-100 text-gray-600" };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${s.cls}`}>
      {s.label}
    </span>
  );
}
