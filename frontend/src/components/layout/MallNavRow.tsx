"use client";

import { Link, usePathname } from "@/i18n/navigation";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";

import { useAuthStore } from "@/stores/authStore";
import { ZoneNavMenu } from "./ZoneNavMenu";

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
    "relative self-stretch inline-flex items-center whitespace-nowrap font-extrabold text-[13px] sm:text-[14px] px-2 sm:px-3 transition-colors -mb-px";

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
            ? "text-teal-900 border-b-[3px] border-lime"
            : "text-ink-2 hover:text-teal-900"
        }`}
      >
        {t(link.labelKey)}
      </Link>
    );
  };

  return (
    <nav
      className="sticky top-0 md:top-[82px] z-[70] bg-white border-b border-line"
      style={{ boxShadow: "0 1px 2px rgba(18,59,50,.04)" }}
    >
      <div className="mx-auto flex min-h-[44px] max-w-mall items-center gap-4 px-3 sm:min-h-[50px] sm:px-6">
        {/* 只有链接区横向滚动;专区入口在滚动区外,链接放不下时也始终可见 */}
        <div className="min-w-0 flex-1 self-stretch overflow-x-auto scrollbar-hide">
          <div className="flex h-full min-w-max items-stretch gap-0">
            {navLinks.map(renderNavLink)}
          </div>
        </div>
        {zones.length > 0 && (
          <div className="flex shrink-0 items-center border-l border-line pl-4">
            <ZoneNavMenu zones={zones} />
          </div>
        )}
      </div>
    </nav>
  );
}
