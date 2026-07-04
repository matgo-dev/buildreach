"use client";
import { useCallback, useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, Loader2, Plus, Search, X } from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { ApiError } from "@/lib/api";
import { Permissions } from "@/lib/permissions";
import {
  zoneGrantsApi,
  type ZoneBrief,
  type ZoneGrantOut,
} from "@/lib/api/zoneGrants";
import { searchBuyerOrgs, type BuyerOrgBrief } from "@/lib/api/operatorBuyers";

function Inner() {
  const [zones, setZones] = useState<ZoneBrief[]>([]);
  const [zoneCode, setZoneCode] = useState<string>("");
  const [grants, setGrants] = useState<ZoneGrantOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [assignOpen, setAssignOpen] = useState(false);
  const [busyOrgId, setBusyOrgId] = useState<number | null>(null);
  const [toast, setToast] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const showToast = (kind: "ok" | "err", text: string) => {
    setToast({ kind, text });
    setTimeout(() => setToast(null), 3000);
  };

  // 初始:加载专区列表,默认选中第一个
  useEffect(() => {
    void (async () => {
      try {
        const list = await zoneGrantsApi.listZones();
        setZones(list);
        if (list.length > 0) setZoneCode(list[0].code);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "加载专区失败");
      }
    })();
  }, []);

  const loadGrants = useCallback(async (code: string) => {
    if (!code) return;
    setLoading(true);
    setError("");
    try {
      setGrants(await zoneGrantsApi.listGrants(code));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载授权列表失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadGrants(zoneCode);
  }, [zoneCode, loadGrants]);

  const onRevoke = async (g: ZoneGrantOut) => {
    if (!confirm(`确定撤销「${g.name}」对该专区的访问权?\n撤销后该组织成员立即无法浏览/下单专区商品。`)) return;
    setBusyOrgId(g.buyer_org_id);
    try {
      await zoneGrantsApi.revoke(zoneCode, g.buyer_org_id);
      await loadGrants(zoneCode);
      showToast("ok", `已撤销 ${g.name}`);
    } catch (e) {
      showToast("err", e instanceof ApiError ? e.message : "撤销失败");
    } finally {
      setBusyOrgId(null);
    }
  };

  const currentZone = zones.find((z) => z.code === zoneCode);

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">专区授权</h1>
          <p className="mt-1 text-sm text-slate-500">
            给买家组织授权访问央企专区。授权后该组织的成员即可浏览并对专区商品发起询价;撤销后立即失效。
          </p>
        </div>
        <button
          onClick={() => setAssignOpen(true)}
          disabled={!zoneCode}
          className="flex h-10 items-center gap-2 rounded-lg bg-[#003366] px-4 text-sm font-semibold text-white shadow-sm hover:bg-[#002244] disabled:opacity-50"
        >
          <Plus className="h-4 w-4" /> 新增授权
        </button>
      </header>

      {/* 专区选择器(当前只有一个,预留多专区) */}
      <div className="flex items-center gap-3">
        <label className="text-sm font-medium text-slate-600">专区</label>
        <select
          value={zoneCode}
          onChange={(e) => setZoneCode(e.target.value)}
          className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-800 focus:border-[#003366] focus:outline-none focus:ring-2 focus:ring-[#003366]/15"
        >
          {zones.length === 0 && <option value="">暂无专区</option>}
          {zones.map((z) => (
            <option key={z.id} value={z.code}>
              {z.name_zh}（{z.code}）{z.status !== "ACTIVE" ? " · 已停用" : ""}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border-l-4 border-red-500 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-4 py-3 text-left font-semibold">组织 ID</th>
              <th className="px-4 py-3 text-left font-semibold">组织名称</th>
              <th className="px-4 py-3 text-left font-semibold">编码</th>
              <th className="px-4 py-3 text-left font-semibold">授权时间</th>
              <th className="px-4 py-3 text-left font-semibold whitespace-nowrap">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-400">
                  <Loader2 className="inline h-4 w-4 animate-spin" /> 加载中…
                </td>
              </tr>
            )}
            {!loading && grants.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-400">
                  该专区暂无授权组织
                </td>
              </tr>
            )}
            {!loading &&
              grants.map((g) => (
                <tr key={g.buyer_org_id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">#{g.buyer_org_id}</td>
                  <td className="px-4 py-3 text-slate-800">{g.name}</td>
                  <td className="px-4 py-3 text-slate-600">{g.code ?? "—"}</td>
                  <td className="px-4 py-3 text-slate-600">
                    {g.granted_at ? g.granted_at.slice(0, 10) : "—"}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <button
                      disabled={busyOrgId === g.buyer_org_id}
                      onClick={() => onRevoke(g)}
                      className="rounded border border-red-300 px-3 py-1 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
                    >
                      撤销
                    </button>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {toast && (
        <div
          className={
            "fixed bottom-6 right-6 flex items-center gap-2 rounded-lg px-4 py-3 text-sm shadow-lg " +
            (toast.kind === "ok" ? "bg-emerald-600 text-white" : "bg-red-600 text-white")
          }
        >
          {toast.kind === "ok" ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
          {toast.text}
        </div>
      )}

      {assignOpen && currentZone && (
        <AssignModal
          zone={currentZone}
          grantedOrgIds={new Set(grants.map((g) => g.buyer_org_id))}
          onClose={() => setAssignOpen(false)}
          onGranted={async (name) => {
            setAssignOpen(false);
            await loadGrants(zoneCode);
            showToast("ok", `已授权 ${name}`);
          }}
        />
      )}
    </div>
  );
}

function AssignModal({
  zone,
  grantedOrgIds,
  onClose,
  onGranted,
}: {
  zone: ZoneBrief;
  grantedOrgIds: Set<number>;
  onClose: () => void;
  onGranted: (name: string) => Promise<void>;
}) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<BuyerOrgBrief[]>([]);
  const [searching, setSearching] = useState(false);
  const [submittingId, setSubmittingId] = useState<number | null>(null);
  const [err, setErr] = useState("");

  // 防抖搜索买家组织
  useEffect(() => {
    let alive = true;
    setSearching(true);
    const t = setTimeout(async () => {
      try {
        const data = await searchBuyerOrgs(q.trim(), 1, 20);
        if (alive) setResults(data.items);
      } catch (e) {
        if (alive) setErr(e instanceof ApiError ? e.message : "搜索失败");
      } finally {
        if (alive) setSearching(false);
      }
    }, 300);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [q]);

  const onPick = async (org: BuyerOrgBrief) => {
    setSubmittingId(org.id);
    setErr("");
    try {
      await zoneGrantsApi.grant(zone.code, org.id);
      await onGranted(org.name);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "授权失败");
      setSubmittingId(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="flex max-h-[80vh] w-full max-w-md flex-col rounded-2xl bg-white p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">
            授权买家组织 · {zone.name_zh}
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="relative mb-3">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="按组织名搜索…"
            className="h-10 w-full rounded-lg border border-slate-200 bg-white pl-9 pr-3 text-sm text-slate-800 placeholder-slate-400 focus:border-[#003366] focus:outline-none focus:ring-2 focus:ring-[#003366]/15"
          />
        </div>

        {err && (
          <div className="mb-3 flex items-center gap-2 rounded-md border-l-4 border-red-500 bg-red-50 px-3 py-2 text-sm text-red-700">
            <AlertCircle className="h-4 w-4" /> {err}
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-y-auto rounded-lg border border-slate-100">
          {searching && (
            <div className="px-4 py-6 text-center text-sm text-slate-400">
              <Loader2 className="inline h-4 w-4 animate-spin" /> 搜索中…
            </div>
          )}
          {!searching && results.length === 0 && (
            <div className="px-4 py-6 text-center text-sm text-slate-400">无匹配组织</div>
          )}
          {!searching &&
            results.map((org) => {
              const already = grantedOrgIds.has(org.id);
              return (
                <div
                  key={org.id}
                  className="flex items-center justify-between gap-3 border-b border-slate-50 px-4 py-2.5 last:border-b-0"
                >
                  <div className="min-w-0">
                    <div className="truncate text-sm text-slate-800">{org.name}</div>
                    <div className="font-mono text-xs text-slate-400">
                      #{org.id}
                      {org.code ? ` · ${org.code}` : ""}
                    </div>
                  </div>
                  {already ? (
                    <span className="shrink-0 rounded bg-slate-100 px-2 py-1 text-xs text-slate-400">
                      已授权
                    </span>
                  ) : (
                    <button
                      disabled={submittingId === org.id}
                      onClick={() => onPick(org)}
                      className="flex shrink-0 items-center gap-1 rounded-lg bg-[#003366] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#002244] disabled:opacity-60"
                    >
                      {submittingId === org.id && <Loader2 className="h-3 w-3 animate-spin" />}
                      授权
                    </button>
                  )}
                </div>
              );
            })}
        </div>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <RouteGuard requiredPermissions={[Permissions.ZONE_MANAGE]}>
      <Inner />
    </RouteGuard>
  );
}
