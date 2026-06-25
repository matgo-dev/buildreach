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
  ];

  return (
    <PublicLayout>
      <div className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-2xl font-black text-[#00505a] mb-2">{t("privacy.title")}</h1>
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
