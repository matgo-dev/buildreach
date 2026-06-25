"use client";

import { useTranslations } from "next-intl";
import { PublicLayout } from "@/components/layout/PublicLayout";

export default function TermsPage() {
  const t = useTranslations("legal");

  const sections = [
    { title: t("terms.s1_title"), content: t("terms.s1_content") },
    { title: t("terms.s2_title"), content: t("terms.s2_content") },
    { title: t("terms.s3_title"), content: t("terms.s3_content") },
    { title: t("terms.s4_title"), content: t("terms.s4_content") },
    { title: t("terms.s5_title"), content: t("terms.s5_content") },
    { title: t("terms.s6_title"), content: t("terms.s6_content") },
    { title: t("terms.s7_title"), content: t("terms.s7_content") },
    { title: t("terms.s8_title"), content: t("terms.s8_content") },
  ];

  return (
    <PublicLayout>
      <div className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-2xl font-black text-[#00505a] mb-2">{t("terms.title")}</h1>
        <p className="text-sm text-gray-400 mb-8">{t("terms.lastUpdated")}</p>
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
