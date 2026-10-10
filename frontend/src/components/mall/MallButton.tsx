"use client";

import { type ButtonHTMLAttributes, type ReactNode } from "react";
import { Link } from "@/i18n/navigation";

type Variant = "teal" | "lime" | "outline" | "whatsapp";

// 主操作深绿实底白字;lime 为品牌强调(柠绿底必须配深绿字);outline 为次操作。
export const MALL_BTN_OUTLINE = "border-[1.5px] border-teal-700 text-teal-700 font-bold bg-white hover:bg-teal-50";

const STYLES: Record<Variant, string> = {
  teal: "mall-btn-primary font-bold",
  lime: "bg-lime text-teal-900 font-bold hover:bg-lime-soft",
  outline: MALL_BTN_OUTLINE,
  whatsapp: "bg-whatsapp text-white font-bold hover:brightness-95",
};

const SIZE_CLS = {
  sm: "h-8 px-3 text-xs rounded-lg",
  md: "h-10 px-5 text-sm rounded-lg",
  lg: "h-12 px-6 text-base rounded-lg",
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
 * Mall 通用按钮 — 4 种变体(teal/lime/outline/whatsapp) × 3 种尺寸。
 *
 * 传 href 渲染为 Link,否则渲染为 button。
 * 仅用于 mall/buyer 页面,不影响 operator/admin。
 */
export function MallButton(props: ButtonProps | LinkProps) {
  const { variant = "teal", size = "md", block = false, children, className = "", ...rest } = props;
  const base = `inline-flex items-center justify-center gap-2 whitespace-nowrap overflow-hidden transition-colors duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sea ${SIZE_CLS[size]} ${STYLES[variant]} ${block ? "w-full" : ""} ${className}`;

  if ("href" in rest && rest.href) {
    const { href, ...linkRest } = rest as LinkProps;
    return (
      <Link href={href} className={base} {...linkRest}>
        {children}
      </Link>
    );
  }

  const btnRest = rest as ButtonProps;
  return (
    <button className={base} {...btnRest}>
      {children}
    </button>
  );
}
