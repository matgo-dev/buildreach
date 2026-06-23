"use client";

import { Link, usePathname } from "@/i18n/navigation";
import { useTranslations } from "next-intl";

/** Mall 导航行 — 白底,底线暖金色。参考 HTML .nav-row */

interface NavLink {
  href: string;
  labelKey: string;
  /** 未接入的功能标灰 */
  disabled?: boolean;
}

const NAV_LINKS: NavLink[] = [
  { href: "/",            labelKey: "navHome" },
  { href: "/how-to-buy",  labelKey: "navHowToBuy" },
  { href: "/mall",        labelKey: "navMall" },
  { href: "/buyer/cart",  labelKey: "navQuoteRequest" },
  { href: "/order-tracking", labelKey: "navMyOrders" },
];

export function MallNavRow() {
  const pathname = usePathname();
  const t = useTranslations("mall");

  return (
    <nav
      className="sticky top-[82px] z-[70] bg-white border-b border-line"
      style={{ boxShadow: "0 1px 2px rgba(16,36,65,.05)" }}
    >
      <div className="mx-auto max-w-mall px-6 flex items-center min-h-[50px] gap-0 overflow-x-auto scrollbar-hide">
        {NAV_LINKS.map((link) => {
          const active =
            link.href === "/"
              ? pathname === "/"
              : pathname === link.href || pathname.startsWith(link.href + "/");

          if (link.disabled) {
            return (
              <span
                key={link.labelKey}
                className="relative h-[50px] inline-flex items-center px-[18px] text-[14px] font-extrabold text-gray-300 whitespace-nowrap cursor-not-allowed select-none"
                title={t("navComingSoon")}
              >
                {t(link.labelKey)}
              </span>
            );
          }

          return (
            <Link
              key={link.href}
              href={link.href}
              className={`relative h-[50px] inline-flex items-center px-[18px] text-[14px] font-extrabold whitespace-nowrap transition-colors -mb-px ${
                active
                  ? "text-teal-800 border-b-[3px] border-gold"
                  : "text-ink-2 hover:text-teal-800"
              }`}
            >
              {t(link.labelKey)}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
