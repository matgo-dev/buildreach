"use client";
import { Link, usePathname } from "@/i18n/navigation";
import { useTranslations, useLocale } from "next-intl";

import { PUBLIC_NAV } from "@/config/navigation";
import { useAuthStore } from "@/stores/authStore";

/** 公开区主导航:中英双语,顶部 header 中央插槽。公开 layout 和工作台 layout 共用。
 *
 * 角色裁剪:SUPPLIER 顶部只显示「首页」—— 信用评估走左侧工作台「信用评分」,
 * 风控/商城/国别/AI 对 SUPPLIER 心智错配(被监管方 / 被采购方),全部隐藏。
 */
export function PublicNav() {
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);
  const isSupplierOnly =
    !!user && user.roles.length > 0 && user.roles.every((r) => r === "SUPPLIER");
  // SUPPLIER 登录后世界观 = 工作台,顶部 nav 整体隐藏(出口走 logo / 工作台切换 / 头像菜单)
  const t = useTranslations("nav");
  const locale = useLocale();
  const items = isSupplierOnly ? [] : PUBLIC_NAV;
  // 专区入口:仅对被授权买家显示(me.zones 非空)—— 纯权限门,公开/未授权用户看不到
  const zones = isSupplierOnly ? [] : user?.zones ?? [];

  const linkClass = (active: boolean) =>
    "relative rounded-md px-3 py-1.5 text-sm font-medium transition-colors duration-200 " +
    (active ? "text-teal-900" : "text-gray-500 hover:bg-slate-50 hover:text-teal-900");
  const activeBar = (
    <span className="absolute bottom-0 left-3 right-3 h-0.5 rounded-full bg-gold" />
  );

  return (
    <nav className="flex items-center gap-1" aria-label="主导航">
      {items.map((item) => {
        // 子路径也算激活(如 /mall/xxx 时高亮"严选商城");工作台路径下全部不激活
        const active =
          item.path === "/"
            ? pathname === "/"
            : pathname === item.path || pathname.startsWith(item.path + "/");
        return (
          <Link key={item.path} href={item.path} className={linkClass(active)}>
            <span className="block text-center leading-tight">
              <span className="block">{t(item.labelKey)}</span>
              {locale === "zh" && item.labelEn && (
                <span className="-mt-0.5 block text-[8px] font-normal text-gray-400">
                  {item.labelEn}
                </span>
              )}
            </span>
            {active && activeBar}
          </Link>
        );
      })}
      {zones.map((z) => {
        const href = `/zone/${z.code}`;
        const active = pathname === href || pathname.startsWith(href + "/");
        const label = locale === "zh" ? z.name_zh : z.name_en || z.name_zh;
        return (
          <Link key={z.code} href={href} className={linkClass(active)}>
            <span className="block text-center leading-tight">
              <span className="block">{label}</span>
              {locale === "zh" && z.name_en && (
                <span className="-mt-0.5 block text-[8px] font-normal text-gray-400">
                  {z.name_en}
                </span>
              )}
            </span>
            {active && activeBar}
          </Link>
        );
      })}
    </nav>
  );
}
