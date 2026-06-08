"use client";

import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { CheckCircle2, AlertCircle, AlertTriangle, X } from "lucide-react";

// ---------- 类型 ----------

type ToastType = "success" | "error" | "warning";

interface ToastItem {
  id: number;
  message: string;
  type: ToastType;
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  warning: (message: string) => void;
}

// ---------- Context ----------

const ToastContext = createContext<ToastContextValue | null>(null);

let _nextId = 0;

const STYLE: Record<ToastType, { bg: string; icon: typeof CheckCircle2; iconColor: string }> = {
  success: { bg: "bg-emerald-50 text-emerald-800 border-emerald-200", icon: CheckCircle2, iconColor: "text-emerald-500" },
  error: { bg: "bg-red-50 text-red-800 border-red-200", icon: AlertCircle, iconColor: "text-red-500" },
  warning: { bg: "bg-amber-50 text-amber-800 border-amber-200", icon: AlertTriangle, iconColor: "text-amber-500" },
};

// ---------- Provider ----------

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const remove = useCallback((id: number) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback((message: string, type: ToastType = "success") => {
    const id = ++_nextId;
    setItems((prev) => [...prev, { id, message, type }]);
    setTimeout(() => remove(id), 4000);
  }, [remove]);

  const ctx: ToastContextValue = {
    toast: push,
    success: useCallback((m: string) => push(m, "success"), [push]),
    error: useCallback((m: string) => push(m, "error"), [push]),
    warning: useCallback((m: string) => push(m, "warning"), [push]),
  };

  return (
    <ToastContext.Provider value={ctx}>
      {children}
      {/* 渲染层 */}
      <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[60] flex flex-col items-center gap-2 pointer-events-none">
        {items.map((item) => {
          const s = STYLE[item.type];
          const Icon = s.icon;
          return (
            <div
              key={item.id}
              className={`pointer-events-auto rounded-lg border px-5 py-3 text-sm font-medium shadow-lg flex items-center gap-2 animate-in fade-in slide-in-from-top-2 ${s.bg}`}
            >
              <Icon className={`h-4 w-4 flex-shrink-0 ${s.iconColor}`} />
              <span>{item.message}</span>
              <button onClick={() => remove(item.id)} className="ml-2 hover:opacity-70">
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

// ---------- Hook ----------

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within <ToastProvider>");
  return ctx;
}
