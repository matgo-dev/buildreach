"use client";

import { useTranslations } from "next-intl";

/* ---------- 数据定义 ---------- */

type ProcessStep = {
  id: string;
  image: string;
  phase: "online" | "offline";
  highlight?: boolean;
};

const PROCESS_STEPS: ProcessStep[] = [
  { id: "P1", image: "sourcing-supplier-vetting.jpg", phase: "online" },
  { id: "P2", image: "rfq-quotation.jpg", phase: "online" },
  { id: "P3", image: "fulfillment-order.jpg", phase: "online" },
  { id: "1", image: "factory-production.jpg", phase: "offline" },
  { id: "2", image: "qc-inspection.jpg", phase: "offline" },
  { id: "3", image: "consolidation-packing.jpg", phase: "offline", highlight: true },
  { id: "4", image: "customs-declaration.jpg", phase: "offline" },
  { id: "5", image: "ocean-freight.jpg", phase: "offline" },
  { id: "6", image: "arrival-dsm-port.jpg", phase: "offline" },
  { id: "7", image: "destination-clearance.jpg", phase: "offline" },
  { id: "8", image: "ddp-delivery.jpg", phase: "offline" },
];

const CONSOLIDATION_IMAGES = [
  { src: "container-consolidation.jpg", alt: "consolidation" },
  { src: "loaded-container.jpg", alt: "loaded container" },
  { src: "warehouse.jpg", alt: "warehouse" },
];

const CERT_BADGES = ["PVoC", "CoC", "ISO 9001", "SGS", "BBS", "KEBS"];

/* ---------- 子组件 ---------- */

/** Hero 区域 */
function HeroSection({ t }: { t: ReturnType<typeof useTranslations> }) {
  return (
    <section
      className="relative overflow-hidden"
      style={{
        background: "linear-gradient(135deg, #00505a 0%, #003a40 100%)",
      }}
    >
      {/* 动画光晕 */}
      <div
        className="absolute inset-0 opacity-20"
        style={{
          background:
            "radial-gradient(ellipse at 20% 50%, rgba(255,255,255,0.15) 0%, transparent 70%)",
          animation: "pulse 4s ease-in-out infinite",
        }}
      />
      <div className="relative mx-auto max-w-5xl px-6 py-16 md:py-20 text-center">
        {/* 路线徽章 */}
        <span className="inline-flex items-center gap-2 rounded-full bg-white/10 border border-white/20 px-4 py-1.5 text-sm text-white/90 mb-6">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          {t("heroTag")}
        </span>
        <h1 className="text-2xl md:text-4xl font-bold text-white mb-4 leading-tight">
          {t("heroTitle")}
        </h1>
        <p className="text-sm md:text-base text-white/70 max-w-2xl mx-auto leading-relaxed">
          {t("heroSub")}
        </p>
      </div>
      {/* pulse 动画 keyframes */}
      <style jsx>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.15; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </section>
  );
}

/** 横向步骤概览条 */
function StepperOverview({ t }: { t: ReturnType<typeof useTranslations> }) {
  return (
    <div className="bg-gray-50 border-b border-gray-200">
      <div className="mx-auto max-w-5xl px-6 py-6">
        {/* 阶段标签 */}
        <div className="flex items-center gap-3 mb-4">
          <span className="text-xs font-semibold text-teal-700 bg-teal-50 border border-teal-200 rounded-full px-3 py-0.5">
            {t("phaseOnline")}
          </span>
          <span className="text-xs text-gray-400">P1 ~ P3</span>
          <span className="flex-1 h-px bg-gray-200" />
          <span className="text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-3 py-0.5">
            {t("phaseOffline")}
          </span>
          <span className="text-xs text-gray-400">1 ~ 8</span>
        </div>
        {/* 步骤条 */}
        <div className="flex items-center gap-0 overflow-x-auto pb-2">
          {PROCESS_STEPS.map((step, i) => {
            const isHighlight = step.highlight;
            return (
              <div key={step.id} className="flex items-center flex-shrink-0">
                <div className="flex flex-col items-center">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                      isHighlight
                        ? "bg-amber-500 text-white ring-2 ring-amber-300"
                        : step.phase === "online"
                          ? "bg-teal-600 text-white"
                          : "bg-gray-300 text-gray-700"
                    }`}
                  >
                    {step.id}
                  </div>
                  <span className="text-[10px] text-gray-500 mt-1 whitespace-nowrap max-w-[60px] text-center leading-tight">
                    {t(`step_${step.id}_label`)}
                  </span>
                </div>
                {i < PROCESS_STEPS.length - 1 && (
                  <div className="w-4 md:w-6 h-0.5 bg-gray-300 mx-0.5 flex-shrink-0" />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/** 垂直时间线 */
function VerticalTimeline({ t }: { t: ReturnType<typeof useTranslations> }) {
  return (
    <section className="mx-auto max-w-5xl px-6 py-12">
      <h2 className="text-xl md:text-2xl font-bold text-gray-800 mb-2 text-center">
        {t("sectionProcess")}
      </h2>
      <p className="text-sm text-gray-500 text-center mb-10">
        {t("sectionProcessSub")}
      </p>

      <div className="relative">
        {/* 中轴线 */}
        <div className="absolute left-1/2 top-0 bottom-0 w-px bg-gray-200 hidden md:block" />

        <div className="space-y-8 md:space-y-12">
          {PROCESS_STEPS.map((step, i) => {
            const isLeft = i % 2 === 0;
            const isHighlight = step.highlight;

            return (
              <div key={step.id} className="relative">
                {/* 中间节点 — 桌面端 */}
                <div className="absolute left-1/2 -translate-x-1/2 top-6 hidden md:flex z-10">
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold shadow-md ${
                      isHighlight
                        ? "bg-amber-500 text-white ring-4 ring-amber-200"
                        : step.phase === "online"
                          ? "bg-teal-600 text-white"
                          : "bg-white text-gray-700 border-2 border-gray-300"
                    }`}
                  >
                    {step.id}
                  </div>
                </div>

                {/* 卡片 — 桌面端左右交替 */}
                <div
                  className={`md:grid md:grid-cols-2 md:gap-12 ${
                    isLeft ? "" : "md:direction-rtl"
                  }`}
                >
                  {/* 内容侧 */}
                  <div
                    className={`${isLeft ? "md:text-right md:pr-8" : "md:col-start-2 md:pl-8"}`}
                  >
                    <div
                      className={`rounded-xl overflow-hidden border shadow-sm transition-shadow hover:shadow-md ${
                        isHighlight
                          ? "border-amber-300 bg-amber-50/50"
                          : "border-gray-200 bg-white"
                      }`}
                    >
                      {/* 图片 */}
                      <div className="aspect-[16/9] overflow-hidden bg-gray-100">
                        <img
                          src={`/images/fulfillment/${step.image}`}
                          alt={t(`step_${step.id}_label`)}
                          loading="lazy"
                          className="w-full h-full object-cover"
                        />
                      </div>
                      {/* 文字 */}
                      <div className="p-4 text-left">
                        <div className="flex items-center gap-2 mb-2">
                          {/* 移动端序号 */}
                          <span
                            className={`md:hidden w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${
                              isHighlight
                                ? "bg-amber-500 text-white"
                                : step.phase === "online"
                                  ? "bg-teal-600 text-white"
                                  : "bg-gray-200 text-gray-700"
                            }`}
                          >
                            {step.id}
                          </span>
                          <h3 className="text-[15px] font-bold text-gray-800">
                            {t(`step_${step.id}_label`)}
                          </h3>
                          {isHighlight && (
                            <span className="text-[10px] font-semibold text-amber-700 bg-amber-100 rounded-full px-2 py-0.5">
                              {t("consolidationTag")}
                            </span>
                          )}
                        </div>
                        <p className="text-[13px] text-gray-600 leading-relaxed">
                          {t(`step_${step.id}_desc`)}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* 占位侧 — 桌面端空列 */}
                  {isLeft ? (
                    <div className="hidden md:block" />
                  ) : (
                    <div className="hidden md:block md:col-start-1 md:row-start-1" />
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

/** 拼柜核心差异 */
function ConsolidationSection({ t }: { t: ReturnType<typeof useTranslations> }) {
  return (
    <section className="bg-gray-50 border-y border-gray-200">
      <div className="mx-auto max-w-5xl px-6 py-12">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
          {/* 左：图片画廊 */}
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2 aspect-[16/9] rounded-xl overflow-hidden">
              <img
                src={`/images/fulfillment/${CONSOLIDATION_IMAGES[0].src}`}
                alt={CONSOLIDATION_IMAGES[0].alt}
                loading="lazy"
                className="w-full h-full object-cover"
              />
            </div>
            {CONSOLIDATION_IMAGES.slice(1).map((img) => (
              <div key={img.src} className="aspect-[4/3] rounded-lg overflow-hidden">
                <img
                  src={`/images/fulfillment/${img.src}`}
                  alt={img.alt}
                  loading="lazy"
                  className="w-full h-full object-cover"
                />
              </div>
            ))}
          </div>

          {/* 右：特点 */}
          <div>
            <span className="inline-block text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-3 py-0.5 mb-3">
              {t("consolidationTag")}
            </span>
            <h2 className="text-xl md:text-2xl font-bold text-gray-800 mb-6 leading-tight">
              {t("consolidationTitle")}
            </h2>
            <div className="space-y-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="flex items-start gap-3">
                  <span className="flex-shrink-0 w-7 h-7 rounded-full bg-teal-600 text-white text-xs font-bold flex items-center justify-center mt-0.5">
                    {i}
                  </span>
                  <div>
                    <div className="text-[14px] font-semibold text-gray-800">
                      {t(`consolidation_point${i}_title`)}
                    </div>
                    <div className="text-[13px] text-gray-500 leading-relaxed">
                      {t(`consolidation_point${i}_desc`)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/** 信任数据卡片 */
function TrustSection({ t }: { t: ReturnType<typeof useTranslations> }) {
  const stats = [
    { valueKey: "trust_stat1_value", labelKey: "trust_stat1_label" },
    { valueKey: "trust_stat2_value", labelKey: "trust_stat2_label" },
    { valueKey: "trust_stat3_value", labelKey: "trust_stat3_label" },
    { valueKey: "trust_stat4_value", labelKey: "trust_stat4_label" },
  ];

  return (
    <section className="bg-[#0D4D4D]">
      <div className="mx-auto max-w-5xl px-6 py-12">
        <h2 className="text-xl md:text-2xl font-bold text-white mb-8 text-center">
          {t("trustTitle")}
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {stats.map((stat) => (
            <div
              key={stat.valueKey}
              className="rounded-xl bg-white/10 border border-white/15 p-5 text-center"
            >
              <div className="text-2xl md:text-3xl font-bold text-[#e3a615] mb-1">
                {t(stat.valueKey)}
              </div>
              <div className="text-xs text-white/70">{t(stat.labelKey)}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/** 认证徽章 */
function CertificationsSection({ t }: { t: ReturnType<typeof useTranslations> }) {
  return (
    <section className="mx-auto max-w-5xl px-6 py-12 text-center">
      <h2 className="text-xl md:text-2xl font-bold text-gray-800 mb-2">
        {t("certTitle")}
      </h2>
      <p className="text-sm text-gray-500 mb-8">{t("certSub")}</p>
      <div className="flex flex-wrap justify-center gap-3">
        {CERT_BADGES.map((cert) => (
          <span
            key={cert}
            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 shadow-sm"
          >
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            {cert}
          </span>
        ))}
      </div>
    </section>
  );
}

/** 服务范围声明 */
function BoundarySection({ t }: { t: ReturnType<typeof useTranslations> }) {
  return (
    <section className="bg-gray-50 border-t border-gray-200">
      <div className="mx-auto max-w-5xl px-6 py-10">
        <h2 className="text-lg font-bold text-gray-800 mb-4 text-center">
          {t("boundaryTitle")}
        </h2>
        <div className="rounded-xl bg-white border border-gray-200 p-6">
          <div className="flex flex-wrap gap-3 justify-center mb-4">
            {/* 范围图例 */}
            <span className="inline-flex items-center gap-1.5 text-xs text-gray-600">
              <span className="w-3 h-3 rounded-sm bg-teal-500" />
              {t("boundaryIncluded")}
            </span>
            <span className="inline-flex items-center gap-1.5 text-xs text-gray-600">
              <span className="w-3 h-3 rounded-sm bg-gray-300" />
              {t("boundaryExcluded")}
            </span>
          </div>
          <p className="text-[13px] text-gray-600 leading-relaxed text-center max-w-3xl mx-auto">
            {t("boundaryDesc")}
          </p>
        </div>
      </div>
    </section>
  );
}

/* ---------- 主组件 ---------- */

export function FulfillmentShowcase() {
  const t = useTranslations("fulfillment");

  return (
    <div>
      <HeroSection t={t} />
      <StepperOverview t={t} />
      <VerticalTimeline t={t} />
      <ConsolidationSection t={t} />
      <TrustSection t={t} />
      <CertificationsSection t={t} />
      <BoundarySection t={t} />
    </div>
  );
}
