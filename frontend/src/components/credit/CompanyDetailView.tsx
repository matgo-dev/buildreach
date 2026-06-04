"use client";
import Link from "next/link";
import React, { useEffect, useState } from "react";
import { ArrowLeft, Globe, Calendar, Banknote, Building2, RefreshCw } from "lucide-react";

import { GradeBadge } from "@/components/credit/GradeBadge";
import { CreditRadarChart } from "@/components/credit/CreditRadarChart";
import { CertificationChips } from "@/components/credit/CertificationChips";
import { AiChatBox } from "@/components/credit/AiChatBox";
import { useAuthStore } from "@/stores/authStore";
import { creditApi, type CompanyDetailOut } from "@/lib/api/credit";

/** 维度级 override 触发后,在该维度子项行末追加的小灰字标注。
 * key = score_dimension_override.code(后端返回 dimension_overrides[].override_rule_code)。
 * 不在表里的 code → 不显示标注,console.warn 一次,降级。
 */
const OVERRIDE_ROW_LABELS: Record<string, string> = {
  DIM2_CERT_FORGED_OR_EXPIRED: "关键证书伪造或过期,维度强制清零",
  DIM3_UNKNOWN: "数据未知,维度按 40% 满分计",
  DIM4_UNRESOLVED_DEFAULTER: "失信未结案,维度一票否决",
};

/** 企业信用详情主视图。
 * BUYER 详情页(/credit/companies/[id])和 SUPPLIER 自家信用页(/supplier/credit)共用。
 *
 * @param hideAi       去掉底部 AI 对话框(SUPPLIER 自家页面不需要)
 * @param hideBackLink 去掉顶部"返回搜索"链接(SUPPLIER 没有搜索入口)
 */
export function CompanyDetailView({
  companyId,
  hideAi = false,
  hideBackLink = false,
}: {
  companyId: number;
  hideAi?: boolean;
  hideBackLink?: boolean;
}) {
  const [data, setData] = useState<CompanyDetailOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const user = useAuthStore((s) => s.user);
  const canRecompute = !!user?.permissions.includes("credit:recompute");

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await creditApi.detail(companyId);
      setData(d);
    } catch (e) {
      setError((e as Error).message || "加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companyId]);

  const handleRecompute = async () => {
    setRecomputing(true);
    try {
      await creditApi.recompute(companyId);
      await load();
    } catch (e) {
      setError((e as Error).message || "重算失败");
    } finally {
      setRecomputing(false);
    }
  };

  if (loading && !data) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-sm text-slate-400">
        加载中…
      </div>
    );
  }
  if (error || !data) {
    return (
      <div className="rounded-xl border border-red-100 bg-red-50 p-8 text-center text-sm text-red-600">
        {error || "无数据"}
      </div>
    );
  }

  const snap = data.snapshot;
  const overrideLabelByDim = new Map<string, string>();
  for (const hit of snap?.dimension_overrides ?? []) {
    const label = OVERRIDE_ROW_LABELS[hit.override_rule_code];
    if (label) {
      overrideLabelByDim.set(hit.dimension_code, label);
    } else {
      console.warn(`Unknown override code: ${hit.override_rule_code}`);
    }
  }

  return (
    <div className="space-y-5">
      {!hideBackLink && (
        <Link
          href="/credit"
          className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-[#003366]"
        >
          <ArrowLeft className="h-4 w-4" />
          返回搜索
        </Link>
      )}

      {/* 顶部:企业名 + 等级 */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <Globe className="h-3.5 w-3.5" />
              <span className="font-mono">{data.country_code}</span>
              {data.registration_no && <span>· 注册号 {data.registration_no}</span>}
            </div>
            <h1 className="mt-1 text-2xl font-bold text-slate-900">{data.name}</h1>
            {data.legal_name_en && (
              <p className="mt-0.5 text-sm text-slate-500">{data.legal_name_en}</p>
            )}
          </div>
          <div className="flex flex-col items-end gap-2">
            <GradeBadge grade={snap?.grade ?? null} size="lg" showTagline />
            {snap && (
              <div className="text-right text-xs text-slate-500">
                综合得分 <span className="text-lg font-bold text-slate-900">{snap.total_score}</span>
                <span className="text-slate-400"> / 100</span>
              </div>
            )}
            {canRecompute && (
              <button
                onClick={handleRecompute}
                disabled={recomputing}
                className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-50"
              >
                <RefreshCw className={"h-3 w-3 " + (recomputing ? "animate-spin" : "")} />
                {recomputing ? "重算中…" : "触发重算"}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 中部:雷达图 + 基本信息卡 */}
      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        {/* 雷达图 */}
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-slate-900">四维评分</h3>
          {snap ? (
            <CreditRadarChart
              dimensions={data.dimensions}
              totalScore={snap.total_score}
            />
          ) : (
            <div className="py-12 text-center text-sm text-slate-400">暂无评分</div>
          )}
          {/* 维度明细列表 */}
          <div className="mt-4 space-y-1.5">
            {data.dimensions.map((d) => (
              <div key={d.code} className="flex items-center justify-between text-xs">
                <span className="text-slate-600">{d.name}</span>
                <span className="font-medium text-slate-900">
                  {d.score} <span className="text-slate-400">/ {d.max_score}</span>
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* 基本信息卡 */}
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-slate-900">企业基本信息</h3>
          {data.basic ? (
            <dl className="space-y-2 text-sm">
              <InfoRow icon={Calendar} label="成立日期" value={data.basic.established_date} />
              <InfoRow icon={Banknote} label="注册资本" value={data.basic.registered_capital} />
              <InfoRow icon={Building2} label="法定代表人" value={data.basic.legal_representative} />
              <InfoRow label="经营范围" value={data.basic.business_scope} truncate />
              <InfoRow label="股东与股权" value={data.basic.shareholders} truncate />
              <InfoRow label="存续状态" value={data.basic.status_text} />
              <InfoRow label="地址" value={data.basic.address} truncate />
              {data.basic.website && (
                <div className="flex gap-3 text-xs">
                  <span className="w-16 shrink-0 text-slate-400">官网</span>
                  <a
                    href={data.basic.website}
                    target="_blank"
                    rel="noreferrer"
                    className="truncate text-[#003366] hover:underline"
                  >
                    {data.basic.website}
                  </a>
                </div>
              )}
            </dl>
          ) : (
            <div className="text-sm text-slate-400">暂无工商基本信息</div>
          )}
        </div>
      </div>

      {/* 证书 chip */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h3 className="mb-3 text-sm font-semibold text-slate-900">资质认证</h3>
        <CertificationChips certifications={data.certifications} />
      </div>

      {/* 12 子项明细 */}
      <details className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <summary className="cursor-pointer text-sm font-semibold text-slate-900">
          12 个子项明细
        </summary>
        <div className="mt-3 overflow-x-auto">
          <SubitemTable data={data} overrideLabelByDim={overrideLabelByDim} />
        </div>
      </details>

      {/* AI 对话框(SUPPLIER 自家页面 hideAi=true 不渲染) */}
      {!hideAi && (
        <AiChatBox companyId={data.id} aiSummary={snap?.ai_summary ?? null} />
      )}
    </div>
  );
}

function InfoRow({
  icon: Icon,
  label,
  value,
  truncate = false,
}: {
  icon?: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | null | undefined;
  truncate?: boolean;
}) {
  return (
    <div className="flex gap-3 text-xs">
      <span className="flex w-16 shrink-0 items-center gap-1 text-slate-400">
        {Icon && <Icon className="h-3 w-3" />}
        {label}
      </span>
      <span className={"flex-1 text-slate-700 " + (truncate ? "truncate" : "")}>
        {value || <span className="text-slate-300">—</span>}
      </span>
    </div>
  );
}

/** 12 子项明细表:维度列按维度跨行合并;触发维度级 override 的 3 行在"命中规则"列追加一行小灰字。 */
function SubitemTable({
  data,
  overrideLabelByDim,
}: {
  data: CompanyDetailOut;
  overrideLabelByDim?: Map<string, string>;
}) {
  // 按 dimension_code 分组,保持后端返回顺序(dim 1-4)
  const groups: Array<{
    code: string;
    name: string;
    rows: typeof data.details;
    score: number;
    maxScore: number;
  }> = [];

  for (const d of data.details) {
    let g = groups.find((x) => x.code === d.dimension_code);
    if (!g) {
      const dim = data.dimensions.find((x) => x.code === d.dimension_code);
      g = {
        code: d.dimension_code,
        name: d.dimension_name,
        rows: [],
        score: dim?.score ?? 0,
        maxScore: dim?.max_score ?? 0,
      };
      groups.push(g);
    }
    g.rows.push(d);
  }

  return (
    <table className="min-w-full text-xs">
      <thead className="bg-slate-50 text-slate-500">
        <tr>
          <th className="w-44 px-3 py-2 text-left">维度</th>
          <th className="px-3 py-2 text-left">子项</th>
          <th className="w-20 px-3 py-2 text-right">得分</th>
          <th className="px-3 py-2 text-left">命中规则</th>
        </tr>
      </thead>
      <tbody>
        {groups.map((g) => (
          <React.Fragment key={g.code}>
            {g.rows.map((d, idx) => (
              <tr
                key={d.subitem_code}
                className="border-t border-slate-100 hover:bg-slate-50"
              >
                {idx === 0 && (
                  <td
                    rowSpan={g.rows.length}
                    className="align-top border-r border-slate-100 px-3 py-2 text-slate-700"
                  >
                    <div className="font-medium">{g.name}</div>
                    <div className="mt-0.5 text-[11px] text-slate-400">
                      {g.score} / {g.maxScore}
                    </div>
                  </td>
                )}
                <td className="px-3 py-2 text-slate-900">{d.subitem_name}</td>
                <td className="px-3 py-2 text-right font-medium">
                  {d.score} <span className="text-slate-400">/ {d.max_score}</span>
                </td>
                <td className="px-3 py-2 text-slate-500">
                  {d.is_default_score ? (
                    <span className="text-amber-600">(默认分)</span>
                  ) : (
                    d.hit_rule_description || "—"
                  )}
                  {overrideLabelByDim?.get(d.dimension_code) && (
                    <div className="mt-0.5 text-[11px] text-slate-500">
                      {overrideLabelByDim.get(d.dimension_code)}
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </React.Fragment>
        ))}
      </tbody>
    </table>
  );
}
