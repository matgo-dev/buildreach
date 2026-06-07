"use client";

import { useTranslations } from "next-intl";
import { MessageCircle, Search, ShieldCheck, Truck, CreditCard, FileCheck } from "lucide-react";

export function RightSidebar() {
  const t = useTranslations("mall");

  return (
    <div className="space-y-3">
      {/* Quick Sourcing */}
      <div className="rounded-xl border border-green-200 bg-green-50 p-4">
        <div className="flex items-center gap-2 mb-2">
          <Search className="h-4 w-4 text-green-700" />
          <span className="text-sm font-bold text-green-700">{t("quickSourcing")}</span>
        </div>
        <p className="mb-3 text-xs text-green-600">{t("quickSourcingHint")}</p>
        <button
          disabled
          title={t("comingSoon")}
          className="w-full rounded-lg bg-[#0D4D4D] py-2 text-xs font-semibold text-white opacity-60 cursor-not-allowed"
        >
          {t("requestQuote")}
        </button>
      </div>

      {/* WhatsApp */}
      <div className="rounded-xl border border-gray-200 bg-white p-4">
        <div className="flex items-center gap-2 mb-1">
          <MessageCircle className="h-4 w-4 text-green-600" />
          <span className="text-sm font-bold text-gray-800">WhatsApp</span>
        </div>
        <p className="text-xs text-gray-600">+255 697 123 456</p>
        <p className="text-[10px] text-gray-400">{t("whatsappHours")}</p>
      </div>

      {/* Trust Marks */}
      <div className="rounded-xl border border-gray-200 bg-white p-4">
        <p className="mb-2 text-sm font-bold text-gray-800">{t("trustMarks")}</p>
        <ul className="space-y-1.5 text-xs text-gray-500">
          <li className="flex items-center gap-2">
            <ShieldCheck className="h-3.5 w-3.5 text-[#0D4D4D]" />
            {t("trustVerified")}
          </li>
          <li className="flex items-center gap-2">
            <FileCheck className="h-3.5 w-3.5 text-[#0D4D4D]" />
            {t("trustCertified")}
          </li>
          <li className="flex items-center gap-2">
            <CreditCard className="h-3.5 w-3.5 text-[#0D4D4D]" />
            {t("trustPrice")}
          </li>
          <li className="flex items-center gap-2">
            <Truck className="h-3.5 w-3.5 text-[#0D4D4D]" />
            {t("trustDelivery")}
          </li>
        </ul>
      </div>
    </div>
  );
}
