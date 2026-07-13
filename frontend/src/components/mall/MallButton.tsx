"use client";

import { type ButtonHTMLAttributes, type ReactNode } from "react";
import { Link } from "@/i18n/navigation";

type Variant = "teal" | "gold" | "outline" | "whatsapp";

const STYLES: Record<Variant, { className: string; style: React.CSSProperties }> = {
  teal: {
    className: "text-white font-extrabold",
    style: {
      background: "linear-gradient(135deg, #10b981, #0c9468, #0a7a56)",
      boxShadow: "0 6px 16px rgba(0,63,70,.22)",
    },
  },
  gold: {
    className: "text-white font-extrabold",
    style: {
      background: "linear-gradient(135deg, #f0b734, #e3a615, #c1850b)",
      boxShadow: "0 10px 24px rgba(193,133,11,.4)",
    },
  },
  outline: {
    className: "border-[1.5px] border-teal-700 text-teal-800 font-extrabold bg-white hover:bg-teal-50",
    style: {},
  },
  whatsapp: {
    className: "text-white font-extrabold",
    style: {
      background: "linear-gradient(135deg, #2bd86e, #1aa851)",
      boxShadow: "0 8px 20px rgba(37,211,102,.4)",
    },
  },
};

const SIZE_CLS = {
  sm: "h-8 px-3 text-xs rounded-lg",
  md: "h-10 px-5 text-sm rounded-[10px]",
  lg: "h-12 px-6 text-base rounded-[10px]",
};

interface CommonProps {
  variant?: Variant;
  size?: "sm" | "md" | "lg";
  /** 占满宽度 */
  block?: boolean;
  children: ReactNode;
  className?: string;
}

type ButtonProps = CommonProps & ButtonHTMLAttributes<HTMLButtonElement> & { href?: undefined };
type LinkProps = CommonProps & { href: string; target?: string; rel?: string };

/**
 * Mall 通用按钮 — 4 种变体(teal/gold/outline/whatsapp) × 3 种尺寸。
 *
 * 传 href 渲染为 Link,否则渲染为 button。
 * 仅用于 mall/buyer 页面,不影响 operator/admin。
 */
export function MallButton(props: ButtonProps | LinkProps) {
  const { variant = "teal", size = "md", block = false, children, className = "", ...rest } = props;
  const v = STYLES[variant];
  const base = `inline-flex items-center justify-center gap-2 whitespace-nowrap overflow-hidden transition-all hover:-translate-y-px ${SIZE_CLS[size]} ${v.className} ${block ? "w-full" : ""} ${className}`;

  if ("href" in rest && rest.href) {
    const { href, ...linkRest } = rest as LinkProps;
    return (
      <Link href={href} className={base} style={v.style} {...linkRest}>
        {children}
      </Link>
    );
  }

  const btnRest = rest as ButtonProps;
  return (
    <button className={base} style={v.style} {...btnRest}>
      {children}
    </button>
  );
}
