"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { ShoppingCart, FileText } from "lucide-react";
import { useCartStore } from "@/stores/cartStore";

/**
 * 询价申请子 Tab 导航 — 询价篮 / 我的询价单
 * 放在 cart 和 rfqs 两个页面顶部，提供稳定的互切入口。
 */
export function RfqTabNav() {
  const locale = useLocale();
  const pathname = usePathname();
  const tCart = useTranslations("cart");
  const tRfq = useTranslations("rfq");
  const cartCount = useCartStore((s) => s.count);

  const tabs = [
    {
      key: "cart",
      href: `/${locale}/buyer/cart`,
      label: tCart("title"),
      icon: ShoppingCart,
      badge: cartCount > 0 ? cartCount : null,
    },
    {
      key: "rfqs",
      href: `/${locale}/buyer/rfqs`,
      label: tRfq("title"),
      icon: FileText,
      badge: null,
    },
  ];

  return (
    <div className="flex items-center rounded-xl border border-gray-200 bg-white px-2">
      {tabs.map((tab) => {
        const isActive = pathname.startsWith(tab.href);
        const Icon = tab.icon;
        return (
          <Link
            key={tab.key}
            href={tab.href}
            className={`relative inline-flex items-center gap-2 px-5 py-3.5 text-sm font-medium transition-colors ${
              isActive
                ? "text-[#00505a] after:absolute after:bottom-0 after:left-2 after:right-2 after:h-[2.5px] after:rounded-full after:bg-[#00505a]"
                : "text-gray-400 hover:text-gray-600"
            }`}
          >
            <Icon className="h-4 w-4" />
            {tab.label}
            {tab.badge != null && (
              <span className="inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-[#00505a] px-1.5 text-xs font-medium text-white">
                {tab.badge}
              </span>
            )}
          </Link>
        );
      })}
    </div>
  );
}
