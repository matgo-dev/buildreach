"use client";

import { Loader2 } from "lucide-react";

interface ToggleProps {
  checked: boolean;
  onChange: () => void;
  label?: string;
  disabled?: boolean;
  loading?: boolean;
  title?: string;
  size?: "sm" | "md";
}

export default function Toggle({ checked, onChange, label, disabled, loading, title, size = "sm" }: ToggleProps) {
  const track = size === "sm" ? "h-4 w-7" : "h-5 w-9";
  const thumb = size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5";
  const onPos = size === "sm" ? "translate-x-[13px]" : "translate-x-[18px]";
  const offPos = "translate-x-[2px]";

  return (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); onChange(); }}
      disabled={disabled || loading}
      title={title}
      className="inline-flex items-center gap-1.5 disabled:opacity-50"
    >
      {loading ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400" />
      ) : (
        <span className={`relative inline-flex ${track} items-center rounded-full transition-colors ${checked ? "bg-emerald-500" : "bg-slate-300"}`}>
          <span className={`inline-block ${thumb} rounded-full bg-white shadow transition-transform ${checked ? onPos : offPos}`} />
        </span>
      )}
      {label && <span className={`text-[11px] font-medium ${checked ? "text-emerald-700" : "text-slate-600"}`}>{label}</span>}
    </button>
  );
}
