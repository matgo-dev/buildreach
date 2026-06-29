"use client";

import { Suspense, useCallback } from "react";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { MessageCircle } from "lucide-react";
import { Link, useRouter, usePathname } from "@/i18n/navigation";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { ContactPopover } from "@/components/mall/ContactPopover";
import { FulfillmentShowcase } from "@/components/how-to-buy/FulfillmentShowcase";

/* ---------- step 配色 ---------- */

const STEP_COLORS = [
  { bg: "bg-teal-50",    border: "border-teal-500",   text: "text-teal-700",    dot: "bg-teal-500" },
  { bg: "bg-amber-50",   border: "border-amber-500",  text: "text-amber-700",   dot: "bg-amber-500" },
  { bg: "bg-sky-50",     border: "border-sky-500",    text: "text-sky-700",     dot: "bg-sky-500" },
  { bg: "bg-violet-50",  border: "border-violet-500", text: "text-violet-700",  dot: "bg-violet-500" },
  { bg: "bg-orange-50",  border: "border-orange-500", text: "text-orange-700",  dot: "bg-orange-500" },
  { bg: "bg-indigo-50",  border: "border-indigo-500", text: "text-indigo-700",  dot: "bg-indigo-500" },
  { bg: "bg-emerald-50", border: "border-emerald-500",text: "text-emerald-700", dot: "bg-emerald-500" },
] as const;

const STEP_ICONS = ["🔍", "📝", "💰", "🛒", "🏭", "🚢", "✅"];

const FAQ_COUNT = 6;

/* ---------- Components ---------- */

/** 单步卡片 — 左侧序号条 + 右侧内容 */
function StepCard({
  index,
  title,
  desc,
  detail,
}: {
  index: number;
  title: string;
  desc: string;
  detail: string;
}) {
  const c = STEP_COLORS[index];
  const icon = STEP_ICONS[index];

  return (
    <div
      className={`rounded-xl border ${c.border} ${c.bg} overflow-hidden transition-shadow hover:shadow-md`}
    >
      <div className="flex">
        {/* 左侧色条 + 序号 */}
        <div
          className={`flex flex-col items-center justify-center w-[56px] flex-shrink-0 ${c.dot} text-white`}
        >
          <span className="text-lg">{icon}</span>
          <span className="text-xs font-bold mt-0.5">{index + 1}</span>
        </div>
        {/* 右侧内容 */}
        <div className="flex-1 px-5 py-4">
          <h3 className={`text-[15px] font-bold ${c.text} mb-1`}>{title}</h3>
          <p className="text-[13px] text-gray-600 leading-relaxed mb-1.5">
            {desc}
          </p>
          <p className="text-[12px] text-gray-400 leading-relaxed">{detail}</p>
        </div>
      </div>
    </div>
  );
}

const TABS = [
  { key: "buy", labelKey: "tabBuy" },
  { key: "fulfillment", labelKey: "tabFulfillment" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

function HowToBuyContent() {
  const t = useTranslations("howToBuy");
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const tabParam = searchParams.get("tab");
  const activeTab: TabKey = tabParam === "fulfillment" ? "fulfillment" : "buy";

  const setActiveTab = useCallback((tab: TabKey) => {
    const params = new URLSearchParams(searchParams.toString());
    if (tab === "buy") {
      params.delete("tab");
    } else {
      params.set("tab", tab);
    }
    const qs = params.toString();
    router.replace(`${pathname}${qs ? `?${qs}` : ""}`);
  }, [searchParams, router, pathname]);

  const phases = [
    { icon: "🔍", labelKey: "phaseSelect" },
    { icon: "📝", labelKey: "phaseRfq" },
    { icon: "💰", labelKey: "phaseQuote" },
    { icon: "🛒", labelKey: "phaseOrder" },
    { icon: "🏭", labelKey: "phaseFulfill" },
    { icon: "🚢", labelKey: "phaseShip" },
    { icon: "✅", labelKey: "phaseComplete" },
  ];

  return (
    <PublicLayout>
      {/* ===== Tab 切换 — 箭头流程式 ===== */}
      <div className="bg-white border-b border-gray-200">
        <div className="mx-auto max-w-mall px-6 py-3 flex items-center">
          {TABS.map((tab, i) => {
            const isActive = activeTab === tab.key;
            const isFirst = i === 0;
            const isLast = i === TABS.length - 1;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`relative flex items-center justify-center text-sm font-medium transition-all h-9 ${
                  isFirst ? "pl-4 pr-6 rounded-l-lg" : "pl-7 pr-6"
                } ${isLast ? "rounded-r-lg" : ""} ${
                  isActive
                    ? "bg-[#00505a] text-white"
                    : "bg-gray-100 text-gray-500 hover:bg-gray-200 hover:text-gray-700"
                }`}
                style={{
                  clipPath: isLast
                    ? undefined
                    : "polygon(0 0, calc(100% - 12px) 0, 100% 50%, calc(100% - 12px) 100%, 0 100%)",
                }}
              >
                {t(tab.labelKey)}
                {/* 非首个 tab 左侧的箭头凹口遮罩 */}
                {!isFirst && (
                  <span
                    className={`absolute left-0 top-0 h-full w-3 ${
                      isActive ? "text-gray-100" : "text-white"
                    }`}
                    style={{
                      clipPath: "polygon(0 0, 100% 50%, 0 100%)",
                      backgroundColor: "currentColor",
                    }}
                  />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* ===== 履约保障 Tab ===== */}
      {activeTab === "fulfillment" && <FulfillmentShowcase />}

      {/* ===== 采购路径 Tab ===== */}
      {activeTab === "buy" && (
      <>
      {/* ===== Hero — 紧凑全宽 ===== */}
      <div className="mx-auto max-w-mall px-6 pt-6">
        <div className="rounded-2xl bg-gradient-to-r from-[#00505a] to-[#003a40] px-6 py-7">
          {/* 上：标题 + stats 同一行 */}
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-5">
            <div>
              <h1 className="text-xl md:text-2xl font-bold text-white mb-1.5">
                {t("heroTitle")}
              </h1>
              <p className="text-[13px] text-white/65 leading-relaxed max-w-lg">
                {t("heroDesc")}
              </p>
            </div>
            {/* Stats — 横排紧凑，移动端自适应 */}
            <div className="grid grid-cols-3 gap-2 lg:flex lg:gap-3 lg:flex-shrink-0">
              <Link
                href="/mall"
                className="flex flex-col items-center rounded-lg bg-white/10 border border-white/15 px-2 py-2.5 lg:px-4 hover:bg-white/15 transition-colors cursor-pointer"
              >
                <span className="text-lg lg:text-xl font-bold text-[#e3a615] leading-none">
                  {t("stat1Value")}
                </span>
                <span className="text-[10px] text-white/60 mt-1 whitespace-nowrap">
                  {t("stat1Label")}
                </span>
              </Link>
              {[2, 3].map((i) => (
                <div
                  key={i}
                  className="flex flex-col items-center rounded-lg bg-white/10 border border-white/15 px-2 py-2.5 lg:px-4"
                >
                  <span className="text-lg lg:text-xl font-bold text-[#e3a615] leading-none">
                    {t(`stat${i}Value`)}
                  </span>
                  <span className="text-[10px] text-white/60 mt-1 whitespace-nowrap">
                    {t(`stat${i}Label`)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* 中：7 步 mini pipeline — 移动端可横滚 */}
          <div className="overflow-x-auto -mx-3 px-3 mb-4">
            <div className="flex items-center justify-center bg-white/[0.06] rounded-lg px-3 py-2 gap-0 min-w-max">
              {phases.map((p, i) => (
                <div key={i} className="flex items-center">
                  <div className="flex flex-col items-center px-2 lg:px-4">
                    <span className="text-base leading-none">{p.icon}</span>
                    <span className="text-[10px] text-white/70 mt-0.5 whitespace-nowrap">
                      {t(p.labelKey)}
                    </span>
                  </div>
                  {i < phases.length - 1 && (
                    <div className="w-3 lg:w-4 h-[1.5px] bg-white/25 flex-shrink-0" />
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* 下：CTA 按钮 */}
          <div className="flex flex-wrap gap-3">
            <Link
              href="/mall"
              className="inline-flex items-center gap-1.5 rounded-lg border border-white/30 bg-white/10 px-5 py-2 text-[13px] font-semibold text-white hover:bg-white/20 transition-colors"
            >
              {t("ctaBrowse")}
            </Link>
            <ContactPopover>
              <button
                className="inline-flex items-center gap-1.5 rounded-lg bg-[#25D366] px-5 py-2 text-[13px] font-semibold text-white hover:bg-[#20bd5a] transition-colors"
              >
                <MessageCircle className="h-4 w-4" />
                {t("ctaRfq")}
              </button>
            </ContactPopover>
          </div>
        </div>
      </div>

      {/* ===== 主体 ===== */}
      <div className="mx-auto max-w-mall px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
          {/* 左：7 步详情 */}
          <div>
            <h2 className="text-lg font-bold text-gray-800 mb-4">
              {t("stepsTitle")}
            </h2>
            <div className="space-y-3">
              {STEP_COLORS.map((_, i) => (
                <StepCard
                  key={i}
                  index={i}
                  title={t(`step${i + 1}Title`)}
                  desc={t(`step${i + 1}Desc`)}
                  detail={t(`step${i + 1}Detail`)}
                />
              ))}
            </div>
          </div>

          {/* 右 sidebar */}
          <div className="space-y-4">
            {/* 平台优势 */}
            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <h3 className="text-[14px] font-bold text-gray-800 mb-3">
                {t("advantagesTitle")}
              </h3>
              <div className="space-y-3">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="flex gap-2.5 items-start">
                    <span className="flex-shrink-0 w-8 h-8 rounded-lg bg-teal-50 text-teal-700 flex items-center justify-center text-sm">
                      {t(`adv${i}Icon`)}
                    </span>
                    <div>
                      <div className="text-[13px] font-semibold text-gray-800">
                        {t(`adv${i}Title`)}
                      </div>
                      <div className="text-[12px] text-gray-500 leading-relaxed">
                        {t(`adv${i}Desc`)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* FAQ */}
            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <h3 className="text-[14px] font-bold text-gray-800 mb-3">
                {t("faqTitle")}
              </h3>
              <div className="space-y-2">
                {Array.from({ length: FAQ_COUNT }, (_, i) => i + 1).map(
                  (i) => (
                    <details key={i} className="group">
                      <summary className="cursor-pointer text-[13px] font-medium text-gray-700 hover:text-teal-700 transition-colors list-none flex items-start gap-2 py-0.5">
                        <span className="text-gray-400 group-open:rotate-90 transition-transform text-[10px] mt-[3px] flex-shrink-0">
                          ▶
                        </span>
                        {t(`faq${i}Q`)}
                      </summary>
                      <p className="mt-1 ml-4 text-[12px] text-gray-500 leading-relaxed pb-1">
                        {t(`faq${i}A`)}
                      </p>
                    </details>
                  ),
                )}
              </div>
            </div>

            {/* CTA */}
            <div className="rounded-xl bg-gradient-to-br from-[#00505a] to-[#003d45] p-4 text-center">
              <p className="text-[13px] text-white/90 font-medium mb-2.5">
                {t("ctaCardText")}
              </p>
              <Link
                href="/buyer/rfqs"
                className="inline-flex items-center gap-1.5 rounded-lg bg-[#e3a615] px-5 py-2 text-[13px] font-semibold text-white hover:bg-[#c99012] transition-colors"
              >
                {t("ctaCardBtn")} →
              </Link>
            </div>
          </div>
        </div>
      </div>
      </>
      )}
    </PublicLayout>
  );
}

export default function HowToBuyPage() {
  return (
    <Suspense fallback={null}>
      <HowToBuyContent />
    </Suspense>
  );
}
