"use client";
import { ReactNode } from "react";

import { AppHeader } from "./AppHeader";
import { PublicNav } from "./PublicNav";

/** 公开区 Layout(顶部单行 nav,无 sidebar)。 */
export function PublicLayout({
  children,
  noContainer = false,
}: {
  children: ReactNode;
  /** 关闭内置 max-w/padding,适合首页等需要全屏 hero 的场景 */
  noContainer?: boolean;
}) {
  return (
    <div className="min-h-screen bg-slate-50">
      <AppHeader centerNav={<PublicNav />} />
      {noContainer ? (
        <main>{children}</main>
      ) : (
        <main className="mx-auto max-w-[1400px] px-6 py-8">{children}</main>
      )}
    </div>
  );
}
