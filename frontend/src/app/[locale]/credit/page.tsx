"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Search, X, Building2, MapPin } from "lucide-react";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { GradeBadge } from "@/components/credit/GradeBadge";
import { COUNTRIES } from "@/config/country-registration-rules";
import {
  creditApi,
  type CompanyListItem,
  type SearchHistoryItem,
} from "@/lib/api/credit";

// 9 国国别下拉(单一可信源:@/config/country-registration-rules · COUNTRIES)
const COUNTRY_OPTIONS: Array<{ code: string; name: string }> = [
  { code: "", name: "全部国家" },
  ...COUNTRIES.map((c) => ({ code: c.code, name: c.nameZh })),
];

function CreditInner() {
  const [country, setCountry] = useState<string>("");
  const [query, setQuery] = useState<string>("");
  const [debounced, setDebounced] = useState<string>("");
  const [results, setResults] = useState<CompanyListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<SearchHistoryItem[]>([]);

  // 输入防抖
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 300);
    return () => clearTimeout(t);
  }, [query]);

  // 搜索(国别变化或 debounced query 变化时触发)
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    creditApi
      .search({ country, q: debounced })
      .then((data) => {
        if (!cancelled) setResults(data);
      })
      .catch(() => {
        if (!cancelled) setResults([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [country, debounced]);

  // 历史
  const refreshHistory = () => {
    creditApi.history().then(setHistory).catch(() => setHistory([]));
  };
  useEffect(() => {
    refreshHistory();
  }, []);

  const handleDeleteHistory = async (id: number) => {
    try {
      await creditApi.deleteHistory(id);
      refreshHistory();
    } catch {
      /* swallow */
    }
  };

  const countryName = useMemo(
    () =>
      COUNTRY_OPTIONS.find((c) => c.code === country)?.name ?? "全部国家",
    [country]
  );

  return (
    <div className="space-y-6">
      {/* Hero */}
      <div className="rounded-2xl bg-gradient-to-br from-[#003366] to-[#0F4C81] px-6 py-8 text-white shadow-sm">
        <h1 className="text-2xl font-bold">信用评估 · 海外工程领域专业版企查查</h1>
        <p className="mt-1 text-sm text-white/80">
          输入国别 + 关键词,查看企业的四维评分(基础工商 / 资质认证 / 财务健康 / 司法舆情)+ AI 综合评价。
        </p>
      </div>

      {/* 搜索条 */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row">
          {/* 国别 */}
          <div className="flex items-center gap-2">
            <MapPin className="h-4 w-4 text-slate-400" />
            <select
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm focus:border-[#003366] focus:outline-none"
            >
              {COUNTRY_OPTIONS.map((c) => (
                <option key={c.code || "ALL"} value={c.code}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          {/* 关键词 */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="企业名 / 英文名 / 注册号关键词"
              className="w-full rounded-md border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm focus:border-[#003366] focus:outline-none"
            />
          </div>
        </div>
        <p className="mt-2 text-xs text-slate-400">
          数据范围:{countryName}
          {debounced ? ` · 关键词 "${debounced}"` : ""}
          {loading ? " · 搜索中…" : ` · 返回 ${results.length} 条`}
        </p>
      </div>

      {/* 结果列表 */}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {results.map((c) => (
          <Link
            key={c.id}
            href={`/credit/companies/${c.id}`}
            className="group rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <Building2 className="h-4 w-4 shrink-0 text-slate-400" />
                  <h3 className="truncate text-sm font-semibold text-slate-900 group-hover:text-[#003366]">
                    {c.name}
                  </h3>
                </div>
                {c.legal_name_en && (
                  <p className="mt-0.5 truncate text-[11px] text-slate-400">
                    {c.legal_name_en}
                  </p>
                )}
                <div className="mt-2 flex items-center gap-3 text-xs text-slate-500">
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono">
                    {c.country_code}
                  </span>
                  {c.registration_no && <span>注册号:{c.registration_no}</span>}
                </div>
              </div>
              <div className="text-right">
                <GradeBadge grade={c.grade} size="md" />
                {typeof c.total_score === "number" && (
                  <div className="mt-1 text-[11px] text-slate-400">
                    {c.total_score} / 100
                  </div>
                )}
              </div>
            </div>
          </Link>
        ))}
        {!loading && results.length === 0 && (
          <div className="col-span-full rounded-xl border border-dashed border-slate-200 bg-white p-8 text-center text-sm text-slate-400">
            未找到匹配企业。试试更换国别或调整关键词。
            <br />
            <span className="text-[11px]">
              注:第一阶段候选库仅含 4 家 demo 企业(seed 数据);真实数据源接入见 TODO T-2。
            </span>
          </div>
        )}
      </div>

      {/* 近期搜索 */}
      {history.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
            近期搜索({history.length})
          </h3>
          <div className="space-y-1.5">
            {history.map((h) => (
              <div
                key={h.id}
                className="flex items-center gap-3 rounded-md px-2 py-1.5 hover:bg-slate-50"
              >
                <Link
                  href={`/credit/companies/${h.company_id}`}
                  className="flex-1 truncate text-sm text-slate-700 hover:text-[#003366]"
                >
                  {h.company_name}
                  <span className="ml-2 text-[11px] text-slate-400">
                    {h.country_code}
                  </span>
                </Link>
                <GradeBadge grade={h.grade} size="sm" />
                <button
                  onClick={() => handleDeleteHistory(h.id)}
                  title="删除此条历史"
                  className="rounded p-1 text-slate-300 hover:bg-slate-100 hover:text-slate-600"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function CreditPage() {
  return (
    <PublicLayout>
      <RouteGuard>
        <CreditInner />
      </RouteGuard>
    </PublicLayout>
  );
}
