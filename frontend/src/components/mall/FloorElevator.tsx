"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUp } from "lucide-react";
import { useTranslations } from "next-intl";

export interface FloorItem {
  id: string;       // 对应楼层 DOM id
  nameKey: string;  // i18n key
}

/**
 * 楼层电梯 — 鑫方盛风格。
 *
 * - fixed 定位在页面左侧，不占楼层内容宽度
 * - 第一个楼层快滚完、第二个楼层露出时才出现
 * - 楼层区域完全滚过后隐藏
 */
export function FloorElevator({ floors }: { floors: FloorItem[] }) {
  const t = useTranslations("mall");
  const [activeId, setActiveId] = useState(floors[0]?.id ?? "");
  const [visible, setVisible] = useState(false);
  const ratioMap = useRef<Map<string, number>>(new Map());

  // ── 显隐：第一个楼层底部接近视口顶部时出现，楼层区完全滚过后隐藏 ──
  useEffect(() => {
    const firstFloor = floors[0] ? document.getElementById(floors[0].id) : null;
    const container = document.getElementById("category-floors-container");
    if (!firstFloor || !container) return;

    const onScroll = () => {
      const firstRect = firstFloor.getBoundingClientRect();
      const containerRect = container.getBoundingClientRect();
      setVisible(firstRect.bottom < 150 && containerRect.bottom > 200);
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, [floors]);

  // ── 高亮：追踪每个楼层的可见比例 ──
  useEffect(() => {
    const map = ratioMap.current;
    map.clear();

    const obs = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          map.set(entry.target.id, entry.isIntersecting ? entry.intersectionRatio : 0);
        }
        let bestId: string | null = null;
        let bestRatio = 0;
        for (const [id, ratio] of map) {
          if (ratio > bestRatio) {
            bestRatio = ratio;
            bestId = id;
          }
        }
        if (!bestId) {
          let closestId: string | null = null;
          let closestDist = Infinity;
          for (const floor of floors) {
            const el = document.getElementById(floor.id);
            if (!el) continue;
            const top = el.getBoundingClientRect().top;
            if (top < 200 && Math.abs(top) < closestDist) {
              closestDist = Math.abs(top);
              closestId = floor.id;
            }
          }
          if (closestId) bestId = closestId;
        }
        if (bestId) setActiveId(bestId);
      },
      { threshold: [0, 0.1, 0.3, 0.5, 0.7, 1], rootMargin: "-80px 0px -30% 0px" },
    );

    for (const floor of floors) {
      const el = document.getElementById(floor.id);
      if (el) obs.observe(el);
    }
    return () => obs.disconnect();
  }, [floors]);

  const scrollTo = useCallback((id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  const scrollToTop = useCallback(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  return (
    <div
      className={`hidden lg:block fixed z-30 transition-all duration-300 ${
        visible
          ? "opacity-100 translate-x-0"
          : "opacity-0 -translate-x-4 pointer-events-none"
      }`}
      style={{ top: "50%", left: "max(8px, calc((100vw - 1280px) / 2 - 90px))", transform: `translateY(-50%) ${visible ? "" : "translateX(-16px)"}` }}
    >
      <div
        className="flex flex-col rounded-lg border border-line bg-white overflow-hidden w-[76px]"
        style={{ boxShadow: "0 2px 8px rgba(16,36,65,.08)" }}
      >
        {floors.map((floor) => {
          const isActive = activeId === floor.id;
          return (
            <button
              key={floor.id}
              onClick={() => scrollTo(floor.id)}
              className={`block w-full px-1.5 py-2.5 text-[12px] leading-tight text-center border-b border-gray-100 last:border-b-0 transition-colors ${
                isActive
                  ? "bg-teal-700 text-white font-bold"
                  : "text-gray-600 hover:bg-teal-50 hover:text-teal-800"
              }`}
            >
              {t(floor.nameKey)}
            </button>
          );
        })}
        <button
          onClick={scrollToTop}
          className="block w-full px-1.5 py-2 text-center text-[10px] text-gray-400 hover:text-teal-800 hover:bg-teal-50 transition-colors border-t border-gray-100"
        >
          <ArrowUp className="w-3 h-3 mx-auto mb-0.5" />
          {t("floorBackToTop")}
        </button>
      </div>
    </div>
  );
}
