"use client";

// PRD v1.4 Δ7:离开页 beforeunload 提示。
// 用户在 Step 2/3 已经填了数据,意外关 tab / 刷新 / 后退时,
// 浏览器弹原生确认框。配合 sessionStorage 草稿暂存是双保险。
//
// 注意:自定义 message 在现代浏览器已被禁用,只能用浏览器原生文案。

import { useEffect } from "react";

export function useBeforeUnload(shouldWarn: boolean): void {
  useEffect(() => {
    if (!shouldWarn) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      // 现代浏览器忽略自定义文案,只看 returnValue 是否非空就弹原生提示
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [shouldWarn]);
}
