"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { useTranslations } from "next-intl";

/**
 * 通用「复制回答」按钮 —— 仿主流 AI 对话的复制交互。
 * AI 助手对话气泡与成本测算结果共用;自带 i18n,调用方只需传 text。
 */
export function CopyButton({
  text,
  variant = "outline",
}: {
  text: string;
  /** outline:带边框(结果卡用);ghost:无边框轻量(对话气泡下用) */
  variant?: "outline" | "ghost";
}) {
  const t = useTranslations("aiAssistant");
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // 降级:clipboard 不可用时用临时 textarea
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  const base = "inline-flex items-center gap-1.5 rounded-lg text-xs font-medium transition-colors ";
  const styles =
    variant === "ghost"
      ? "px-1.5 py-1 " + (copied ? "text-teal-600" : "text-slate-400 hover:text-teal-700")
      : "border px-2.5 py-1.5 " +
        (copied
          ? "border-teal-300 bg-teal-50 text-teal-700"
          : "border-slate-200 bg-white text-ink-2 hover:border-teal-300 hover:text-teal-700");

  return (
    <button onClick={handleCopy} className={base + styles}>
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      {copied ? t("ccCopied") : t("ccCopy")}
    </button>
  );
}
