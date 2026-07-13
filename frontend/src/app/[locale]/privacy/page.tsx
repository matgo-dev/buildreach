"use client";

import { useTranslations } from "next-intl";
import { PublicLayout } from "@/components/layout/PublicLayout";

export default function PrivacyPage() {
  const t = useTranslations("legal");

  const sections = [
    { title: t("privacy.s1_title"), content: t("privacy.s1_content") },
    { title: t("privacy.s2_title"), content: t("privacy.s2_content") },
    { title: t("privacy.s3_title"), content: t("privacy.s3_content") },
    { title: t("privacy.s4_title"), content: t("privacy.s4_content") },
    { title: t("privacy.s5_title"), content: t("privacy.s5_content") },
    { title: t("privacy.s6_title"), content: t("privacy.s6_content") },
    { title: t("privacy.s7_title"), content: t("privacy.s7_content") },
    { title: t("privacy.s8_title"), content: t("privacy.s8_content") },
    { title: t("privacy.s9_title"), content: t("privacy.s9_content") },
    { title: t("privacy.s10_title"), content: t("privacy.s10_content") },
    { title: t("privacy.s11_title"), content: t("privacy.s11_content") },
    { title: t("privacy.s12_title"), content: t("privacy.s12_content") },
    { title: t("privacy.s13_title"), content: t("privacy.s13_content") },
    { title: t("privacy.s14_title"), content: t("privacy.s14_content") },
    { title: t("privacy.s15_title"), content: t("privacy.s15_content") },
  ];

  return (
    <PublicLayout>
      <div className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-2xl font-black text-[#0c9468] mb-2">{t("privacy.title")}</h1>
        <p className="text-sm text-gray-400 mb-8">{t("privacy.lastUpdated")}</p>
        <div className="space-y-6">
          {sections.map((s, i) => (
            <section key={i}>
              <h2 className="text-base font-bold text-gray-800 mb-2">{`${i + 1}. ${s.title}`}</h2>
              <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-line">{s.content}</p>
            </section>
          ))}
        </div>
      </div>
    </PublicLayout>
  );
}
