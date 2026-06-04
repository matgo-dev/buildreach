"use client";
import { useEffect, useMemo, useState } from "react";
import { Search, Globe, ChevronRight } from "lucide-react";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { ScoreCircle } from "@/components/supplier/ScoreCircle";
import { Permissions } from "@/config/permission-matrix";
import { COUNTRIES } from "@/config/country-registration-rules";
import { suppliersApi, type SupplierListItem, type Grade } from "@/lib/api/suppliers";

// grade → tier(展示层映射,不落库)
const TIER_META: Record<Grade, { label: string; cls: string }> = {
  A: { label: "T1 头部供应商", cls: "bg-amber-100 text-amber-700" },
  B: { label: "T2 优质供应商", cls: "bg-slate-200 text-slate-600" },
  C: { label: "T3 认证供应商", cls: "bg-orange-100 text-orange-700" },
  D: { label: "暂未评级", cls: "bg-slate-100 text-slate-400" },
};

const COUNTRY_NAME: Record<string, string> = Object.fromEntries(
  COUNTRIES.map((c) => [c.code, c.nameZh])
);

// 级别筛选 chip → grade
const LEVELS: Array<{ key: string; label: string; grade: string }> = [
  { key: "T1", label: "T1 头部", grade: "A" },
  { key: "T2", label: "T2 优质", grade: "B" },
  { key: "T3", label: "T3 认证", grade: "C" },
];

function TierBadge({ grade }: { grade: Grade | null }) {
  const meta = grade ? TIER_META[grade] : null;
  return (
    <span
      className={
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium " +
        (meta ? meta.cls : "bg-slate-100 text-slate-400")
      }
    >
      {meta ? meta.label : "评分生成中"}
    </span>
  );
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={
        "rounded-full px-3 py-1 text-sm transition-colors " +
        (active
          ? "bg-[#003366] text-white"
          : "bg-slate-100 text-slate-600 hover:bg-slate-200")
      }
    >
      {children}
    </button>
  );
}

function SuppliersInner() {
  const [items, setItems] = useState<SupplierListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [keyword, setKeyword] = useState("");
  const [submittedQ, setSubmittedQ] = useState("");
  const [country, setCountry] = useState("");
  const [level, setLevel] = useState(""); // "" | T1 | T2 | T3

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const grade = LEVELS.find((l) => l.key === level)?.grade ?? "";
    suppliersApi
      .list({ q: submittedQ, country, grade })
      .then((d) => {
        if (!cancelled) setItems(d);
      })
      .catch(() => {
        if (!cancelled) setItems([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [submittedQ, country, level]);

  // banner 统计(基于当前返回列表)
  const stats = useMemo(() => {
    let t1 = 0, t2 = 0, t3 = 0;
    for (const s of items) {
      if (s.grade === "A") t1++;
      else if (s.grade === "B") t2++;
      else if (s.grade === "C") t3++;
    }
    return { total: items.length, t1, t2, t3 };
  }, [items]);

  return (
    <div className="space-y-6">
      {/* Banner */}
      <div className="flex items-center justify-between rounded-2xl bg-gradient-to-r from-[#003366] to-[#0a4f8a] px-8 py-7 text-white">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">认证供应商目录</h1>
            <span className="rounded-full bg-[#FF6B35] px-2.5 py-0.5 text-sm font-medium">
              {stats.total} 家
            </span>
          </div>
          <p className="mt-1.5 text-sm text-blue-100">严格筛选 · 多维评分 · 放心合作</p>
        </div>
        <div className="hidden gap-8 sm:flex">
          {[
            { n: stats.t1, label: "T1 头部" },
            { n: stats.t2, label: "T2 优质" },
            { n: stats.t3, label: "T3 认证" },
          ].map((x) => (
            <div key={x.label} className="text-center">
              <div className="text-2xl font-bold">{x.n}</div>
              <div className="text-xs text-blue-100">{x.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 搜索 + 筛选 */}
      <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && setSubmittedQ(keyword.trim())}
              placeholder="搜索供应商名称…"
              className="w-full rounded-lg border border-slate-200 py-2 pl-9 pr-3 text-sm outline-none focus:border-[#003366]"
            />
          </div>
          <button
            onClick={() => setSubmittedQ(keyword.trim())}
            className="rounded-lg bg-[#003366] px-5 text-sm font-medium text-white hover:bg-[#00284d]"
          >
            搜索
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="mr-1 text-sm text-slate-400">国家:</span>
          <Chip active={country === ""} onClick={() => setCountry("")}>全部国家</Chip>
          {COUNTRIES.map((c) => (
            <Chip key={c.code} active={country === c.code} onClick={() => setCountry(c.code)}>
              {c.nameZh}
            </Chip>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="mr-1 text-sm text-slate-400">级别:</span>
          <Chip active={level === ""} onClick={() => setLevel("")}>全部级别</Chip>
          {LEVELS.map((l) => (
            <Chip key={l.key} active={level === l.key} onClick={() => setLevel(l.key)}>
              {l.label}
            </Chip>
          ))}
        </div>
      </div>

      {/* 列表 */}
      {loading ? (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-sm text-slate-400">
          加载中…
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-sm text-slate-400">
          未找到匹配供应商
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((s) => (
            <div
              key={s.id}
              className="flex flex-col rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
            >
              <div className="flex items-start justify-between gap-3">
                <h3 className="text-base font-bold text-slate-900">{s.name}</h3>
                <ScoreCircle score={s.total_score} />
              </div>
              <div className="mt-3">
                <TierBadge grade={s.grade} />
              </div>
              <div className="mt-3 flex items-center gap-1.5 text-xs text-slate-500">
                <Globe className="h-3.5 w-3.5" />
                <span>{COUNTRY_NAME[s.country_code] ?? s.country_code}</span>
              </div>
              <div className="mt-4 border-t border-slate-100 pt-3 text-right">
                {/* TODO: 供应商详情页待实现,本期占位不可点 */}
                <span className="inline-flex cursor-not-allowed items-center gap-0.5 text-sm text-slate-300">
                  查看详情 <ChevronRight className="h-4 w-4" />
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function SuppliersDirectoryPage() {
  return (
    <PublicLayout>
      <RouteGuard requiredPermissions={[Permissions.SUPPLIER_READ]}>
        <SuppliersInner />
      </RouteGuard>
    </PublicLayout>
  );
}
