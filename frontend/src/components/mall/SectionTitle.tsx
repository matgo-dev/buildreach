"use client";

import { type ReactNode } from "react";

interface Props {
  /** 中文主标题 */
  children: ReactNode;
  /** 英文副标题(大写显示) */
  sub?: string;
  /** 右侧插槽(如"查看全部"链接) */
  right?: ReactNode;
  className?: string;
}

/**
 * Mall 区块标题 — 左侧金→青渐变竖条 + 双语。
 *
 * 仅用于 mall/buyer 页面,不影响 operator/admin。
 */
export function SectionTitle({ children, sub, right, className = "" }: Props) {
  return (
    <div className={`flex items-end justify-between gap-4 ${className}`}>
      <h2 className="relative pl-3.5 text-xl font-black text-navy leading-tight before:content-[''] before:absolute before:left-0 before:top-[0.15em] before:bottom-[0.15em] before:w-1 before:rounded before:bg-gradient-to-b before:from-gold before:to-teal-700">
        {children}
        {sub && (
          <span className="ml-2 text-[11px] font-extrabold text-teal-700 uppercase tracking-widest">
            {sub}
          </span>
        )}
      </h2>
      {right && <div className="shrink-0">{right}</div>}
    </div>
  );
}
