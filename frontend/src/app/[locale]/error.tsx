"use client";

import { useEffect } from "react";
import { useParams } from "next/navigation";
import { AlertTriangle, Home, RotateCw } from "lucide-react";
import { routing } from "@/i18n/routing";

// 文案内置而不走 next-intl:错误边界不能依赖出错的那棵树(provider 异常、
// 或发版前打开的标签页里 messages 还没有这些 key),否则兜底页自己也会坏。
// 以 routing.locales 为键:新增语言而漏了这里会直接编译报错,而不是静默回落英文。
type Locale = (typeof routing.locales)[number];

const TEXT: Record<Locale, { title: string; description: string; retry: string; goHome: string; detailLabel: string }> = {
  zh: {
    title: "页面出错了",
    description: "页面遇到了意外错误。请刷新重试；如果仍然出现，请把此页面截图发给我们。",
    retry: "刷新重试",
    goHome: "返回首页",
    detailLabel: "错误信息",
  },
  en: {
    title: "Something went wrong",
    description:
      "This page hit an unexpected error. Please reload; if it keeps happening, send us a screenshot of this page.",
    retry: "Reload",
    goHome: "Back to home",
    detailLabel: "Error details",
  },
  sw: {
    title: "Hitilafu imetokea",
    description:
      "Ukurasa huu umepata hitilafu isiyotarajiwa. Tafadhali pakia upya; ikiendelea, tutumie picha ya skrini ya ukurasa huu.",
    retry: "Pakia upya",
    goHome: "Rudi mwanzo",
    detailLabel: "Maelezo ya hitilafu",
  },
};

const DETAIL_MAX_LENGTH = 300;

/**
 * [locale] 段错误边界:页面渲染抛异常时兜底,避免整页白屏。
 * 错误信息直接展示在页面上——当前没有前端错误上报通道,用户截图即可定位。
 */
export default function LocaleError({
  error,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const params = useParams();
  const locale: Locale =
    routing.locales.find((l) => l === params?.locale) ?? routing.defaultLocale;
  const text = TEXT[locale];
  // localePrefix: "as-needed" —— 默认语言不带前缀
  const homeHref = locale === routing.defaultLocale ? "/" : `/${locale}`;

  useEffect(() => {
    console.error(error);
  }, [error]);

  // 截断:message 可能夹带数据(如回显的响应体),页面上只留够定位的长度
  const fullDetail = [error.name, error.message].filter(Boolean).join(": ");
  const detail =
    fullDetail.length > DETAIL_MAX_LENGTH ? `${fullDetail.slice(0, DETAIL_MAX_LENGTH)}…` : fullDetail;

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 p-6">
      <div className="w-full max-w-md text-center">
        <div className="mx-auto mb-6 flex h-24 w-24 items-center justify-center rounded-full bg-slate-100">
          <AlertTriangle className="h-12 w-12 text-slate-400" strokeWidth={1.5} />
        </div>

        <h1 className="text-2xl font-bold text-slate-800">{text.title}</h1>
        <p className="mt-3 text-sm text-slate-500">{text.description}</p>

        <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
          {/* 整页重载而非 reset():chunk 加载失败/发版后旧标签页,reset 只会重渲染到同一个错误 */}
          <button
            onClick={() => window.location.reload()}
            className="inline-flex h-10 items-center gap-2 rounded-lg bg-slate-800 px-5 text-sm font-medium text-white shadow-sm transition hover:bg-slate-700"
          >
            <RotateCw className="h-4 w-4" />
            {text.retry}
          </button>
          {/* 用原生 <a> 整页跳转:出错后客户端路由状态不可信 */}
          <a
            href={homeHref}
            className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-200 bg-white px-5 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50"
          >
            <Home className="h-4 w-4" />
            {text.goHome}
          </a>
        </div>

        {/* translate="no":错误原文不能被浏览器翻译改写,否则截图无法检索 */}
        <div translate="no" className="notranslate mt-8 rounded-lg bg-slate-100 px-4 py-3 text-left">
          <p className="text-[11px] font-medium text-slate-400">{text.detailLabel}</p>
          <p className="mt-1 break-words font-mono text-xs text-slate-500">
            {detail}
            {error.digest ? ` (${error.digest})` : ""}
          </p>
        </div>
      </div>
    </div>
  );
}
