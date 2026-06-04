"use client";

import * as React from "react";

import {
  CategoryCascader,
  EMPTY_CATEGORY,
  type SelectedCategory,
} from "@/components/category/CategoryCascader";

/**
 * 商品三级分类联动 demo 页(本轮临时,后续轮次接入真实页面后可删)。
 * 路由:/test/category
 *
 * 用途:Step 7 手工验证 CategoryCascader 行为(对齐 PRD §8 前端验收清单)。
 * 不入主导航。
 */
export default function CategoryCascaderTestPage() {
  const [selected, setSelected] =
    React.useState<SelectedCategory>(EMPTY_CATEGORY);

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-8">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold text-slate-900">
          商品三级分类联动 · Demo
        </h1>
        <p className="text-sm text-slate-500">
          PRD: <code>docs/商品三级分类-PRD-v1.0.md</code> · 仅本地验证使用
        </p>
      </header>

      <CategoryCascader value={selected} onChange={setSelected} required />

      <section className="rounded-md border border-slate-200 bg-slate-50 p-4">
        <h2 className="mb-2 text-sm font-medium text-slate-700">
          当前选择(SelectedCategory)
        </h2>
        <pre className="overflow-auto text-xs leading-relaxed text-slate-700">
          {JSON.stringify(selected, null, 2)}
        </pre>
      </section>

      <section className="rounded-md border border-slate-200 p-4 text-sm text-slate-600">
        <h2 className="mb-2 font-medium text-slate-700">手工验收(PRD §8)</h2>
        <ul className="list-inside list-disc space-y-1">
          <li>选 L1 → L2 下拉重算,且 L3 已被清空 + disabled</li>
          <li>选 L2 → L3 下拉重算</li>
          <li>L1 改变 → L2 / L3 自动清空</li>
          <li>未登录态也能访问(API 公开)</li>
          <li>数据正常 4 个一级:土建工程 / 安装材料 / 装饰工程 / 品牌专区</li>
        </ul>
      </section>
    </div>
  );
}
