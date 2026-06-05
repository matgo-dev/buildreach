"use client";

import { ShieldCheck, FileCheck, DollarSign, Truck, Globe, CheckCircle } from "lucide-react";

const TRUST_ITEMS = [
  { icon: <ShieldCheck className="h-6 w-6" />, zh: "优质供应商", en: "Verified Suppliers" },
  { icon: <FileCheck className="h-6 w-6" />, zh: "认证齐全", en: "PVoC / CoC Certified" },
  { icon: <DollarSign className="h-6 w-6" />, zh: "价格更优", en: "Competitive Price" },
  { icon: <Truck className="h-6 w-6" />, zh: "快速交付", en: "Fast Delivery" },
  { icon: <CheckCircle className="h-6 w-6" />, zh: "安全付款", en: "Secure Payment" },
  { icon: <Globe className="h-6 w-6" />, zh: "合规进口", en: "Import Compliant" },
];

export function MallFooter() {
  return (
    <footer className="border-t border-slate-200 bg-white py-5">
      <div className="mx-auto flex max-w-[1280px] items-center justify-between px-4">
        {TRUST_ITEMS.map((item) => (
          <div key={item.en} className="flex items-center gap-2">
            <div className="text-[#0D4D4D]">{item.icon}</div>
            <div>
              <p className="text-[12px] font-medium text-slate-800">{item.zh}</p>
              <p className="text-[10px] text-slate-400">{item.en}</p>
            </div>
          </div>
        ))}
      </div>
    </footer>
  );
}
