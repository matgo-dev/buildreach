"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/navigation";
import { zoneDisplayName, type ZoneBriefForUser } from "@/lib/zoneName";

/**
 * 导航行的专区入口。账号能看到的专区数从 1 到很多都要成立:
 * - 1 个:直接是一个带专区名的入口(下拉里只有一项等于多点一次);名字过长截断 + title 显示全名。
 * - ≥2 个:固定宽度的「专区 ▾」按钮 + 浮层列表;浮层限高、内部滚动,长名换行不截断。
 *
 * 为什么不平铺:导航行宽度有上限(max-w-mall),实测 3 个专区时中文溢出 226px、
 * 2 个专区也会溢出,行内又是 overflow-x-auto + 隐藏滚动条,溢出的专区直接看不见。
 * 收进一个按钮后宽度与专区数量无关。
 *
 * 浮层用 position:fixed:导航行是横向滚动容器,absolute 子元素会被它裁掉。
 */
export function ZoneNavMenu({ zones }: { zones: ZoneBriefForUser[] }) {
  const t = useTranslations("mall");
  const locale = useLocale();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; right: number } | null>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const activeCode = zones.find((z) => pathname === `/zone/${z.code}` || pathname.startsWith(`/zone/${z.code}/`))?.code;

  const place = useCallback(() => {
    const r = btnRef.current?.getBoundingClientRect();
    if (r) setPos({ top: r.bottom + 6, right: Math.max(8, window.innerWidth - r.right) });
  }, []);

  useEffect(() => {
    if (!open) return;
    place();
    const close = () => setOpen(false);
    const onDown = (e: MouseEvent) => {
      const target = e.target as Node;
      if (!panelRef.current?.contains(target) && !btnRef.current?.contains(target)) close();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        close();
        btnRef.current?.focus();
      }
    };
    // 页面/导航滚动会让 fixed 浮层和按钮错位 → 收起;浮层自己内部滚动(专区多时)不收
    const onScroll = (e: Event) => {
      if (!panelRef.current?.contains(e.target as Node)) close();
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", close);
    window.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", close);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [open, place]);

  // 路由切换后收起
  useEffect(() => setOpen(false), [pathname]);

  const chipCls = (active: boolean) =>
    `inline-flex h-8 items-center gap-1 whitespace-nowrap rounded-full border px-3 text-[13px] font-extrabold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 ${
      active
        ? "border-lime bg-lime/30 text-teal-900"
        : "border-line bg-teal-50 text-teal-900 hover:border-teal-200 hover:bg-teal-100"
    }`;

  if (zones.length === 1) {
    const z = zones[0];
    const name = zoneDisplayName(z, locale);
    return (
      <Link
        href={`/zone/${z.code}`}
        title={name}
        aria-current={activeCode ? "page" : undefined}
        className={`${chipCls(!!activeCode)} max-w-[220px]`}
      >
        <span className="truncate">{name}</span>
      </Link>
    );
  }

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        aria-haspopup="true"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className={chipCls(!!activeCode)}
      >
        {t("navZones")}
        <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
      </button>
      {open && pos && (
        <div
          ref={panelRef}
          className="fixed z-[80] max-h-[min(60vh,420px)] min-w-[200px] max-w-[min(320px,calc(100vw-16px))] overflow-y-auto overscroll-contain rounded-lg border border-line bg-white py-1 shadow-mall-lg"
          style={{ top: pos.top, right: pos.right }}
        >
          <ul>
            {zones.map((z) => {
              const active = z.code === activeCode;
              return (
                <li key={z.code}>
                  <Link
                    href={`/zone/${z.code}`}
                    aria-current={active ? "page" : undefined}
                    className={`block px-4 py-2.5 text-[14px] font-bold transition-colors focus-visible:bg-teal-50 focus-visible:outline-none ${
                      active ? "bg-lime/30 text-teal-900" : "text-ink hover:bg-teal-50"
                    }`}
                  >
                    {zoneDisplayName(z, locale)}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </>
  );
}
