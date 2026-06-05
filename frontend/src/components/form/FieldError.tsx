"use client";

/**
 * 表单字段错误提示组件。
 * 红色小字显示在字段下方。
 */
export function FieldError({ error }: { error?: string }) {
  if (!error) return null;
  return <p className="mt-1 text-[12px] text-red-500">{error}</p>;
}
