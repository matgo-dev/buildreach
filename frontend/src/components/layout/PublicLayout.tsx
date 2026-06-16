"use client";
import { ReactNode } from "react";

import { TopStrip } from "./TopStrip";
import { MallHeader } from "./MallHeader";
import { MallNavRow } from "./MallNavRow";
import { MallFooter } from "./MallFooter";

/**
 * 买方前台 Layout — 深青信任风格。
 *
 * 结构:TopStrip → MallHeader → MallNavRow → 内容 → MallFooter
 * 三栏布局由各页面自行组织(mall 页 = 左品类 + 中内容 + 右客服/RFQ)。
 */
export function PublicLayout({
  children,
  noContainer = false,
}: {
  children: ReactNode;
  noContainer?: boolean;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-bg">
      <TopStrip />
      <MallHeader />
      <MallNavRow />
      <main className="flex-1">
        {noContainer ? children : (
          <div className="mx-auto max-w-mall px-6 py-6">
            {children}
          </div>
        )}
      </main>
      <MallFooter />
    </div>
  );
}
