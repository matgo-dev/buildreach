"use client";

import { useEffect } from "react";
import { AlertTriangle, Home, RotateCw } from "lucide-react";
import { useTranslations } from "next-intl";

/**
 * [locale] 段错误边界:页面渲染抛异常时兜底,避免整页白屏。
 * 错误信息直接展示在页面上——当前没有前端错误上报通道,用户截图即可定位。
 */
export default function LocaleError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const t = useTranslations("errorPage");

  useEffect(() => {
    console.error(error);
  }, [error]);

  const detail = [error.name, error.message].filter(Boolean).join(": ");

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 p-6">
      <div className="w-full max-w-md text-center">
        <div className="mx-auto mb-6 flex h-24 w-24 items-center justify-center rounded-full bg-slate-100">
          <AlertTriangle className="h-12 w-12 text-slate-400" strokeWidth={1.5} />
        </div>

        <h1 className="text-2xl font-bold text-slate-800">{t("title")}</h1>
        <p className="mt-3 text-sm text-slate-500">{t("description")}</p>

        <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
          <button
            onClick={reset}
            className="inline-flex h-10 items-center gap-2 rounded-lg bg-slate-800 px-5 text-sm font-medium text-white shadow-sm transition hover:bg-slate-700"
          >
            <RotateCw className="h-4 w-4" />
            {t("retry")}
          </button>
          {/* 用原生 <a> 整页跳转:出错后客户端路由状态不可信 */}
          {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
          <a
            href="/"
            className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-200 bg-white px-5 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50"
          >
            <Home className="h-4 w-4" />
            {t("goHome")}
          </a>
        </div>

        {/* translate="no":错误原文不能被浏览器翻译改写,否则截图无法检索 */}
        <div translate="no" className="notranslate mt-8 rounded-lg bg-slate-100 px-4 py-3 text-left">
          <p className="text-[11px] font-medium text-slate-400">{t("detailLabel")}</p>
          <p className="mt-1 break-words font-mono text-xs text-slate-500">
            {detail}
            {error.digest ? ` (${error.digest})` : ""}
          </p>
        </div>
      </div>
    </div>
  );
}
