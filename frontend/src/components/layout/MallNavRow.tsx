"use client";

import { Link, usePathname } from "@/i18n/navigation";
import { useSearchParams } from "next/navigation";
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
  // 本地采购 / 进口采购 — 初期均复用商品分类页(/mall),内容一致;
  // 本地/进口的区分后续通过 procurement 参数落地筛选。
  { href: "/mall?procurement=local",  labelKey: "navLocalProcurement" },
  { href: "/mall?procurement=import", labelKey: "navImportProcurement" },
  { href: "/buyer/cart",  labelKey: "navQuoteRequest" },
  { href: "/order-tracking", labelKey: "navMyOrders" },
  { href: "/ai-assistant",   labelKey: "navAiAssistant" },
];

export function MallNavRow() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const t = useTranslations("mall");

  return (
    <nav
      className="sticky top-0 md:top-[82px] z-[70] bg-white border-b border-line"
      style={{ boxShadow: "0 1px 2px rgba(16,36,65,.05)" }}
    >
      <div className="mx-auto max-w-mall px-3 sm:px-6 flex items-center min-h-[44px] sm:min-h-[50px] gap-0 overflow-x-auto scrollbar-hide">
        {NAV_LINKS.map((link) => {
          // href 可能带 query(如 /mall?procurement=local),按路径 + query 双匹配高亮,
          // 保证本地/进口两个入口在同一 /mall 页面上仍能各自精确高亮。
          const [linkPath, linkQuery] = link.href.split("?");
          const pathActive =
            linkPath === "/"
              ? pathname === "/"
              : pathname === linkPath || pathname.startsWith(linkPath + "/");
          const active = linkQuery
            ? pathActive &&
              [...new URLSearchParams(linkQuery).entries()].every(
                ([k, v]) => searchParams.get(k) === v
              )
            : pathActive;

          if (link.disabled) {
            return (
              <span
                key={link.labelKey}
                className="relative h-[44px] sm:h-[50px] inline-flex items-center px-3 sm:px-[18px] text-[13px] sm:text-[14px] font-extrabold text-gray-300 whitespace-nowrap cursor-not-allowed select-none"
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
              className={`relative h-[44px] sm:h-[50px] inline-flex items-center px-3 sm:px-[18px] text-[13px] sm:text-[14px] font-extrabold whitespace-nowrap transition-colors -mb-px ${
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
