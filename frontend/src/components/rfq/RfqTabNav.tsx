"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { ShoppingCart, FileText } from "lucide-react";
import { useCartStore } from "@/stores/cartStore";

/**
 * 询价申请子 Tab 导航 — 询价篮 / 询价管理
 * pill 高亮激活态，全宽贴合下方内容。
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
      match: "/buyer/cart",
      label: tCart("title"),
      icon: ShoppingCart,
      badge: cartCount > 0 ? cartCount : null,
    },
    {
      key: "rfqs",
      href: `/${locale}/buyer/rfqs`,
      match: "/buyer/rfqs",
      label: tRfq("title"),
      icon: FileText,
      badge: null,
    },
  ];

  return (
    <div className="flex items-center gap-1 border-b border-gray-200 bg-white rounded-t-xl px-4 py-2">
      {tabs.map((tab) => {
        // pathname 可能带或不带 locale 前缀，两种都匹配
        const isActive = pathname.startsWith(tab.href) || pathname.startsWith(tab.match);
        const Icon = tab.icon;
        return (
          <Link
            key={tab.key}
            href={tab.href}
            className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm transition-colors ${
              isActive
                ? "bg-lime text-teal-900 font-semibold"
                : "text-ink-2 font-medium hover:bg-teal-50 hover:text-teal-900"
            }`}
          >
            <Icon className="h-4 w-4" />
            {tab.label}
            {tab.badge != null && (
              <span className={`inline-flex h-5 min-w-[20px] items-center justify-center rounded-full px-1.5 text-xs font-medium ${
                isActive
                  ? "bg-teal-900/10 text-teal-900"
                  : "bg-teal-700 text-white"
              }`}>
                {tab.badge}
              </span>
            )}
          </Link>
        );
      })}
    </div>
  );
}
