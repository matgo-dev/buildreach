"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { ChevronDown } from "lucide-react";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { useWhatsApp } from "@/hooks/useWhatsApp";

/* ---------- 品类分区配置 ---------- */

interface Section {
  id: string;
  icon: string;
  qCount: number;
}

const SECTIONS: Section[] = [
  { id: "platform",   icon: "🏠", qCount: 6 },
  { id: "tools",      icon: "🔧", qCount: 8 },
  { id: "safety",     icon: "🦺", qCount: 8 },
  { id: "fasteners",  icon: "🔩", qCount: 8 },
  { id: "electrical", icon: "⚡", qCount: 8 },
  { id: "doors",      icon: "🚪", qCount: 8 },
  { id: "decoration", icon: "🎨", qCount: 8 },
];

/* ---------- FAQ 手风琴 ---------- */

function FaqItem({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border-b border-gray-100 last:border-b-0">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-start gap-3 py-3.5 px-1 text-left group"
      >
        <ChevronDown
          className={`h-4 w-4 mt-0.5 flex-shrink-0 text-gray-400 transition-transform ${
            open ? "rotate-0" : "-rotate-90"
          }`}
        />
        <span className="text-[14px] font-medium text-gray-800 group-hover:text-teal-700 transition-colors leading-relaxed">
          {q}
        </span>
      </button>
      {open && (
        <div className="pl-8 pr-2 pb-4">
          <p className="text-[13px] text-gray-600 leading-[1.8] whitespace-pre-line">
            {a}
          </p>
        </div>
      )}
    </div>
  );
}

/* ---------- 主页面 ---------- */

export default function HelpCenterPage() {
  const t = useTranslations("helpCenter");
  const wa = useWhatsApp();
  const [activeSection, setActiveSection] = useState(SECTIONS[0].id);

  const current = SECTIONS.find((s) => s.id === activeSection)!;

  return (
    <PublicLayout>
      {/* 主体 */}
      <div className="mx-auto max-w-mall px-6 pt-1.5 pb-6">
        <div className="rounded-2xl bg-gradient-to-r from-[#00505a] to-[#003a40] px-6 py-7 mb-6">
          <h1 className="text-xl md:text-2xl font-bold text-white mb-2">
            {t("pageTitle")}
          </h1>
          <p className="text-[13px] text-white/65 leading-relaxed max-w-2xl">
            {t("pageDesc")}
          </p>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-6">
          {/* 左侧导航 — sticky + 填满高度 */}
          <div className="lg:sticky lg:top-[140px] lg:self-start flex flex-col gap-4">
            <nav className="rounded-xl border border-gray-200 bg-white overflow-hidden">
              {SECTIONS.map((sec) => (
                <button
                  key={sec.id}
                  onClick={() => setActiveSection(sec.id)}
                  className={`w-full flex items-center gap-2.5 px-4 py-3 text-[13px] font-medium transition-colors text-left border-b border-gray-50 last:border-b-0 ${
                    activeSection === sec.id
                      ? "bg-teal-50 text-teal-800 border-l-[3px] border-l-teal-600"
                      : "text-gray-600 hover:bg-gray-50 hover:text-gray-900 border-l-[3px] border-l-transparent"
                  }`}
                >
                  <span className="text-base">{sec.icon}</span>
                  {t(`${sec.id}_title`)}
                </button>
              ))}
            </nav>

            {/* WhatsApp 联系 */}
            {wa.number && (
              <div className="rounded-xl bg-gradient-to-br from-[#00505a] to-[#003d45] p-4 text-center">
                <p className="text-[12px] text-white/80 mb-2">{t("contactHint")}</p>
                <a
                  href={wa.buildLink() ?? "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 rounded-lg bg-[#25D366] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#1fb855] transition-colors"
                >
                  WhatsApp
                </a>
              </div>
            )}
          </div>

          {/* 右侧内容 */}
          <div>
            <div className="rounded-xl border border-gray-200 bg-white">
              {/* 分区标题 */}
              <div className="border-b border-gray-100 px-6 py-4">
                <h2 className="text-[16px] font-bold text-gray-800 flex items-center gap-2">
                  <span className="text-lg">{current.icon}</span>
                  {t(`${current.id}_title`)}
                </h2>
                <p className="text-[12px] text-gray-400 mt-1">
                  {t(`${current.id}_subtitle`)}
                </p>
              </div>

              {/* FAQ 列表 */}
              <div className="px-6">
                {Array.from({ length: current.qCount }, (_, i) => i + 1).map(
                  (i) => (
                    <FaqItem
                      key={`${current.id}-${i}`}
                      q={t(`${current.id}_q${i}`)}
                      a={t(`${current.id}_a${i}`)}
                    />
                  ),
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </PublicLayout>
  );
}
