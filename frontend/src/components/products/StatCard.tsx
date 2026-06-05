"use client";

interface StatCardProps {
  title: string;
  value: number | string;
  subtitle?: string;
  accentColor: string;
  icon: React.ReactNode;
}

export function StatCard({ title, value, subtitle, accentColor, icon }: StatCardProps) {
  return (
    <div className="relative flex items-center gap-4 overflow-hidden rounded-lg bg-white p-5 shadow-sm">
      <div className="absolute left-0 top-0 h-full w-1" style={{ backgroundColor: accentColor }} />
      <div className="flex-1 pl-2">
        <p className="text-sm text-slate-500">{title}</p>
        <p className="mt-1 text-2xl font-bold text-slate-900">{typeof value === "number" ? value.toLocaleString() : value}</p>
        {subtitle && <p className="mt-0.5 text-xs text-slate-400">{subtitle}</p>}
      </div>
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-50 text-slate-400">
        {icon}
      </div>
    </div>
  );
}
