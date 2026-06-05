"use client";

import { ChevronRight, Home } from "lucide-react";

interface Breadcrumb {
  label: string;
  href?: string;
}

interface AdminPageHeaderProps {
  titleZh: string;
  titleEn: string;
  subtitle?: string;
  breadcrumbs?: Breadcrumb[];
  actions?: React.ReactNode;
}

/**
 * 运营后台统一页面标题区。
 * 对标截图：中英双语标题 + 面包屑 + 右侧操作按钮。
 */
export function AdminPageHeader({ titleZh, titleEn, subtitle, breadcrumbs, actions }: AdminPageHeaderProps) {
  return (
    <div className="space-y-2">
      {/* 面包屑 */}
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav className="flex items-center gap-1 text-[12px] text-slate-400">
          <Home className="h-3 w-3" />
          {breadcrumbs.map((b, i) => (
            <span key={i} className="flex items-center gap-1">
              <ChevronRight className="h-3 w-3" />
              {b.href ? (
                <a href={b.href} className="hover:text-slate-600">{b.label}</a>
              ) : (
                <span className="text-slate-600">{b.label}</span>
              )}
            </span>
          ))}
        </nav>
      )}

      {/* 标题 + 操作 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[20px] font-bold text-slate-900">
            {titleZh}
            <span className="ml-2 text-[14px] font-normal text-slate-400">/ {titleEn}</span>
          </h1>
          {subtitle && <p className="mt-0.5 text-[12px] text-slate-500">{subtitle}</p>}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}
