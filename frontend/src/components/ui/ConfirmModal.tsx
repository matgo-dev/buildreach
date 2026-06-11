"use client";

import { useEffect, useCallback } from "react";
import { useTranslations } from "next-intl";
import { Loader2 } from "lucide-react";

interface ConfirmModalProps {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "primary" | "warning";
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

const VARIANT_STYLES: Record<string, string> = {
  primary: "bg-blue-600 hover:bg-blue-700",
  danger: "bg-red-600 hover:bg-red-700",
  warning: "bg-amber-600 hover:bg-amber-700",
};

export default function ConfirmModal({
  open,
  title,
  description,
  confirmLabel,
  cancelLabel,
  variant = "primary",
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  const tCommon = useTranslations("common");
  const resolvedConfirm = confirmLabel ?? tCommon("confirm");
  const resolvedCancel = cancelLabel ?? tCommon("cancel");
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape" && !loading) onCancel();
    },
    [loading, onCancel]
  );

  useEffect(() => {
    if (!open) return;
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, handleKeyDown]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={() => { if (!loading) onCancel(); }}
    >
      <div
        className="w-full max-w-md bg-white rounded-xl p-6 shadow-2xl mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-base font-semibold text-slate-900">{title}</h3>
        {description && (
          <p className="mt-2 text-sm text-slate-600 whitespace-pre-line">{description}</p>
        )}
        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onCancel}
            disabled={loading}
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {resolvedCancel}
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={`rounded-lg px-4 py-2 text-sm font-medium text-white flex items-center gap-1.5 disabled:opacity-60 ${VARIANT_STYLES[variant]}`}
          >
            {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {resolvedConfirm}
          </button>
        </div>
      </div>
    </div>
  );
}
