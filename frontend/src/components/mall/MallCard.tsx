"use client";

import { type ReactNode } from "react";

interface Props {
  children: ReactNode;
  className?: string;
  /** 内边距,默认 p-4 */
  padding?: string;
  /** 是否可 hover 上浮 */
  hoverable?: boolean;
}

/**
 * Mall 通用卡片容器 — 圆角 + 描边 + 分层阴影。
 *
 * 仅用于 mall/buyer 页面,不影响 operator/admin。
 */
export function MallCard({
  children,
  className = "",
  padding = "p-4",
  hoverable = false,
}: Props) {
  return (
    <div
      className={`rounded-xl border border-line bg-white shadow-mall-sm ${padding} ${
        hoverable ? "transition-all duration-200 hover:-translate-y-0.5 hover:border-teal-700 hover:shadow-mall-md" : ""
      } ${className}`}
    >
      {children}
    </div>
  );
}
