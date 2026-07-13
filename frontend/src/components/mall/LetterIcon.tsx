"use client";

interface Props {
  /** 显示的字母 */
  letter: string;
  /** 是否激活态(实底) */
  active?: boolean;
  /** 尺寸,默认 30px */
  size?: number;
  className?: string;
}

/**
 * 首字母圆角图标 — teal 渐变底 + 白字。
 *
 * 用于品类导航、品类快捷入口。
 * 仅用于 mall/buyer 页面,不影响 operator/admin。
 */
export function LetterIcon({ letter, active = false, size = 30, className = "" }: Props) {
  return (
    <span
      className={`grid place-items-center rounded-[7px] text-xs font-black shrink-0 transition-colors ${
        active ? "bg-teal-700 text-white" : "text-white"
      } ${className}`}
      style={{
        width: size,
        height: size,
        ...(active ? {} : {
          background: "linear-gradient(135deg, #10b981, #0c9468, #0a7a56)",
          boxShadow: "inset 0 1px 0 rgba(255,255,255,.18), 0 4px 10px rgba(0,63,70,.18)",
        }),
      }}
    >
      {letter}
    </span>
  );
}
