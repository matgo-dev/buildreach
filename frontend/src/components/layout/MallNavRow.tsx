"use client";

import { Link, usePathname } from "@/i18n/navigation";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";

import { useAuthStore } from "@/stores/authStore";

/** Mall 导航行 — 白底,底线暖金色。参考 HTML .nav-row */

interface NavLink {
  href: string;
  labelKey: string;
  /** 未接入的功能标灰 */
  disabled?: boolean;
  /** 买家专属操作(购物车/订单),对内部员工(运营/管理员)隐藏 */
  buyerOnly?: boolean;
}

const NAV_LINKS: NavLink[] = [
  { href: "/",            labelKey: "navHome" },
  { href: "/how-to-buy",  labelKey: "navHowToBuy" },
  // 本地采购 / 进口采购 — 初期均复用商品分类页(/mall),内容一致;
  // 本地/进口的区分后续通过 procurement 参数落地筛选。
  { href: "/mall?procurement=local",  labelKey: "navLocalProcurement" },
  { href: "/mall?procurement=import", labelKey: "navImportProcurement" },
  { href: "/buyer/cart",  labelKey: "navQuoteRequest", buyerOnly: true },
  { href: "/order-tracking", labelKey: "navMyOrders", buyerOnly: true },
  { href: "/ai-assistant",   labelKey: "navAiAssistant" },
];

export function MallNavRow() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const t = useTranslations("mall");
  // 专区入口:仅对被授权买家显示(me.zones 非空)—— 纯权限门,公开/未授权用户看不到
  const user = useAuthStore((s) => s.user);
  const zones = user?.zones ?? [];
  // 内部员工(运营/管理员)隐藏买家专属操作(购物车/订单)
  const isStaff = user?.roles?.some((r) => r === "OPERATOR" || r === "ADMIN") ?? false;
  const navLinks = isStaff ? NAV_LINKS.filter((l) => !l.buyerOnly) : NAV_LINKS;

  // 收紧内边距(px-2/sm:px-3),让整排双语项 + 专区一行装下不横滑。
  const itemBase =
    "relative h-[44px] sm:h-[50px] inline-flex items-center whitespace-nowrap font-extrabold text-[13px] sm:text-[14px] px-2 sm:px-3 transition-colors -mb-px";
  const zoneItemBase =
    "inline-flex h-8 items-center gap-1.5 whitespace-nowrap rounded-full border px-3 text-[13px] font-extrabold transition-colors";

  const renderNavLink = (link: NavLink) => {
    // href 可能带 query(如 /mall?procurement=local),按路径 + query 双匹配高亮。
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
          className={`${itemBase} text-gray-300 cursor-not-allowed select-none`}
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
        className={`${itemBase} ${
          active
            ? "text-teal-800 border-b-[3px] border-gold"
            : "text-ink-2 hover:text-teal-800"
        }`}
      >
        {t(link.labelKey)}
      </Link>
    );
  };

  const renderZoneLink = (z: {
    code: string;
    name_zh: string;
    name_en: string | null;
  }) => {
    const href = `/zone/${z.code}`;
    const active = pathname === href || pathname.startsWith(href + "/");
    return (
      <Link
        key={z.code}
        href={href}
        className={`${zoneItemBase} ${
          active
            ? "border-gold bg-teal-50 text-teal-900 shadow-[inset_0_-2px_0_#e3a615]"
            : "border-teal-100 bg-teal-50/70 text-teal-800 hover:border-teal-200 hover:bg-teal-50 hover:text-teal-900"
        }`}
      >
        {z.name_zh}
      </Link>
    );
  };

  return (
    <nav
      className="sticky top-0 md:top-[82px] z-[70] bg-white border-b border-line"
      style={{ boxShadow: "0 1px 2px rgba(16,36,65,.05)" }}
    >
      <div className="mx-auto flex min-h-[44px] max-w-mall items-center justify-between gap-4 overflow-x-auto px-3 scrollbar-hide sm:min-h-[50px] sm:px-6">
        <div className="flex min-w-max items-center gap-0">
          {navLinks.map(renderNavLink)}
        </div>
        {zones.length > 0 && (
          <div className="ml-auto flex shrink-0 items-center gap-2 border-l border-line pl-4">
            <span className="hidden text-[11px] font-semibold text-gray-400 lg:inline">
              {t("navExclusiveZone")}
            </span>
            {zones.map(renderZoneLink)}
          </div>
        )}
      </div>
    </nav>
  );
}
