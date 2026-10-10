"use client";

import { useTranslations } from "next-intl";
import { PublicLayout } from "@/components/layout/PublicLayout";
import { useContactInfo } from "@/hooks/useWhatsApp";

export default function TermsPage() {
  const t = useTranslations("legal");
  // 正文里的联系邮箱/电话取运行时配置(CONTACT_EMAIL / WHATSAPP_DEFAULT_NUMBER),不写死在文案里
  const contact = useContactInfo();
  const vars = { email: contact.email ?? "", phone: contact.whatsappNumber ?? "" };

  const sections = [
    { title: t("terms.s1_title"), content: t("terms.s1_content", vars) },
    { title: t("terms.s2_title"), content: t("terms.s2_content", vars) },
    { title: t("terms.s3_title"), content: t("terms.s3_content", vars) },
    { title: t("terms.s4_title"), content: t("terms.s4_content", vars) },
    { title: t("terms.s5_title"), content: t("terms.s5_content", vars) },
    { title: t("terms.s6_title"), content: t("terms.s6_content", vars) },
    { title: t("terms.s7_title"), content: t("terms.s7_content", vars) },
    { title: t("terms.s8_title"), content: t("terms.s8_content", vars) },
    { title: t("terms.s9_title"), content: t("terms.s9_content", vars) },
    { title: t("terms.s10_title"), content: t("terms.s10_content", vars) },
    { title: t("terms.s11_title"), content: t("terms.s11_content", vars) },
    { title: t("terms.s12_title"), content: t("terms.s12_content", vars) },
    { title: t("terms.s13_title"), content: t("terms.s13_content", vars) },
    { title: t("terms.s14_title"), content: t("terms.s14_content", vars) },
    { title: t("terms.s15_title"), content: t("terms.s15_content", vars) },
    { title: t("terms.s16_title"), content: t("terms.s16_content", vars) },
  ];

  return (
    <PublicLayout>
      <div className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-2xl font-black text-[#0c9468] mb-2">{t("terms.title")}</h1>
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
