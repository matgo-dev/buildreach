"use client";

import { ReactNode, useEffect, useState } from "react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { MallHeader } from "@/components/mall/MallHeader";
import { MallFooter } from "@/components/mall/MallFooter";
import { CategorySidebar, type CategoryItem } from "@/components/mall/CategorySidebar";
import { api } from "@/lib/api";

/**
 * 买方工作台布局 — 对标东非 Demo 截图买方 Dashboard 风格。
 * MallHeader（teal 顶部）+ 左侧品类导航 + 内容区 + MallFooter。
 */
export function BuyerShell({ children }: { children: ReactNode }) {
  const [categories, setCategories] = useState<CategoryItem[]>([]);

  useEffect(() => {
    api.get<CategoryItem[]>("/api/v1/categories?level=1&is_active=true")
      .then(setCategories)
      .catch(console.error);
  }, []);

  return (
    <RouteGuard>
      <div className="flex min-h-screen flex-col bg-[#F5F5F5]">
        <MallHeader />
        <div className="mx-auto flex w-full max-w-[1280px] flex-1 gap-5 px-4 py-5">
          <CategorySidebar
            categories={categories}
            activeCode=""
            onSelect={() => {}}
          />
          <main className="flex-1 min-w-0">{children}</main>
        </div>
        <MallFooter />
      </div>
    </RouteGuard>
  );
}
