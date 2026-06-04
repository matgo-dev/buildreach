"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCircle, Loader2, RefreshCw, X } from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import {
  adminAuditApi,
  type AuditFilterOptions,
  type AuditLogOut,
  type AuditQuery,
} from "@/lib/adminAudit";
import { Permissions } from "@/lib/permissions";

const PAGE_SIZE = 50;

function Inner() {
  const [options, setOptions] = useState<AuditFilterOptions | null>(null);
  const [items, setItems] = useState<AuditLogOut[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState<AuditLogOut | null>(null);

  // 筛选条件
  const [filters, setFilters] = useState<{
    resource_type: string;
    action: string;
    status: string;
    user_email: string;
    trace_id: string;
    start_at: string;
    end_at: string;
  }>({
    resource_type: "",
    action: "",
    status: "",
    user_email: "",
    trace_id: "",
    start_at: "",
    end_at: "",
  });

  const buildQuery = useCallback(
    (p: number): AuditQuery => ({
      page: p,
      page_size: PAGE_SIZE,
      resource_type: filters.resource_type || undefined,
      action: filters.action || undefined,
      status: filters.status || undefined,
      user_email: filters.user_email || undefined,
      trace_id: filters.trace_id || undefined,
      start_at: filters.start_at || undefined,
      end_at: filters.end_at || undefined,
    }),
    [filters]
  );

  const load = useCallback(
    async (p = 1) => {
      setLoading(true);
      setError("");
      try {
        const data = await adminAuditApi.list(buildQuery(p));
        setItems(data.items);
        setTotal(data.total);
        setPage(data.page);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "加载失败");
      } finally {
        setLoading(false);
      }
    },
    [buildQuery]
  );

  // 启动一次拉 options + 第一页数据
  useEffect(() => {
    void adminAuditApi.options().then(setOptions).catch(() => undefined);
  }, []);
  useEffect(() => {
    void load(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const onApply = () => {
    void load(1);
  };
  const onReset = () => {
    setFilters({
      resource_type: "",
      action: "",
      status: "",
      user_email: "",
      trace_id: "",
      start_at: "",
      end_at: "",
    });
    // 重置后立即重拉(借助下次 buildQuery)
    setTimeout(() => void load(1), 0);
  };

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">审计日志</h1>
          <p className="mt-1 text-sm text-slate-500">
            全平台敏感操作审计记录(GET 类查询不入库)。点击行查看完整 extra。
          </p>
        </div>
        <button
          onClick={() => void load(page)}
          className="flex h-9 items-center gap-2 rounded-lg border border-slate-200 px-3 text-sm text-slate-600 hover:bg-slate-50"
        >
          <RefreshCw className="h-4 w-4" /> 刷新
        </button>
      </header>

      {/* 筛选区 */}
      <div className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:grid-cols-2 lg:grid-cols-4">
        <Select
          label="资源类型"
          value={filters.resource_type}
          onChange={(v) => setFilters((s) => ({ ...s, resource_type: v }))}
          options={options?.resource_types ?? []}
        />
        <Select
          label="动作"
          value={filters.action}
          onChange={(v) => setFilters((s) => ({ ...s, action: v }))}
          options={options?.actions ?? []}
        />
        <Select
          label="状态"
          value={filters.status}
          onChange={(v) => setFilters((s) => ({ ...s, status: v }))}
          options={options?.statuses ?? []}
        />
        <TextField
          label="用户邮箱(模糊)"
          value={filters.user_email}
          onChange={(v) => setFilters((s) => ({ ...s, user_email: v }))}
          placeholder="如 @cscec3b"
        />
        <TextField
          label="Trace ID"
          value={filters.trace_id}
          onChange={(v) => setFilters((s) => ({ ...s, trace_id: v }))}
          placeholder="UUID"
        />
        <TextField
          label="起始时间"
          value={filters.start_at}
          onChange={(v) => setFilters((s) => ({ ...s, start_at: v }))}
          placeholder="2026-05-19T00:00:00"
          type="datetime-local"
        />
        <TextField
          label="结束时间"
          value={filters.end_at}
          onChange={(v) => setFilters((s) => ({ ...s, end_at: v }))}
          placeholder="2026-05-19T23:59:59"
          type="datetime-local"
        />
        <div className="flex items-end gap-2">
          <button
            onClick={onApply}
            className="h-10 flex-1 rounded-lg bg-[#003366] text-sm font-semibold text-white hover:bg-[#002244]"
          >
            应用
          </button>
          <button
            onClick={onReset}
            className="h-10 rounded-lg border border-slate-200 px-3 text-sm text-slate-600 hover:bg-slate-50"
          >
            清空
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border-l-4 border-red-500 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {/* 表格 */}
      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-3 py-3 text-left font-semibold">时间</th>
              <th className="px-3 py-3 text-left font-semibold">Trace</th>
              <th className="px-3 py-3 text-left font-semibold">用户</th>
              <th className="px-3 py-3 text-left font-semibold">资源</th>
              <th className="px-3 py-3 text-left font-semibold">动作</th>
              <th className="px-3 py-3 text-left font-semibold">状态</th>
              <th className="px-3 py-3 text-left font-semibold">路径</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-400">
                  <Loader2 className="inline h-4 w-4 animate-spin" /> 加载中…
                </td>
              </tr>
            )}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-400">
                  无匹配记录
                </td>
              </tr>
            )}
            {!loading &&
              items.map((it) => (
                <tr
                  key={it.id}
                  onClick={() => setDetail(it)}
                  className="cursor-pointer hover:bg-slate-50"
                >
                  <td className="px-3 py-2 font-mono text-xs text-slate-600">
                    {formatTime(it.created_at)}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-500" title={it.trace_id}>
                    {it.trace_id.slice(0, 8)}…
                  </td>
                  <td className="px-3 py-2 text-slate-700">{it.user_email ?? "—"}</td>
                  <td className="px-3 py-2 text-slate-700">{it.resource_type}</td>
                  <td className="px-3 py-2 text-slate-700">{it.action}</td>
                  <td className="px-3 py-2">
                    <StatusBadge status={it.status} />
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-500">
                    {it.method ? `${it.method} ` : ""}
                    {it.path ?? "—"}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-slate-500">
          <span>
            共 {total} 条 · 第 {page} / {totalPages} 页
          </span>
          <div className="flex gap-2">
            <button
              disabled={page <= 1 || loading}
              onClick={() => load(page - 1)}
              className="rounded border border-slate-200 px-3 py-1 hover:bg-slate-50 disabled:opacity-40"
            >
              上一页
            </button>
            <button
              disabled={page >= totalPages || loading}
              onClick={() => load(page + 1)}
              className="rounded border border-slate-200 px-3 py-1 hover:bg-slate-50 disabled:opacity-40"
            >
              下一页
            </button>
          </div>
        </div>
      )}

      {detail && <DetailDrawer log={detail} onClose={() => setDetail(null)} />}
    </div>
  );
}

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  // 后端 naive UTC,无 Z。当作 UTC 处理避免时区漂移歧义。
  const d = new Date(iso + (iso.endsWith("Z") ? "" : "Z"));
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}
function pad(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

function StatusBadge({ status }: { status: "SUCCESS" | "FAILED" }) {
  const ok = status === "SUCCESS";
  return (
    <span
      className={
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium " +
        (ok ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700")
      }
    >
      {status}
    </span>
  );
}

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: string[];
}) {
  return (
    <div className="space-y-1">
      <Label className="text-xs font-semibold text-slate-600">{label}</Label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 focus:border-[#003366] focus:outline-none focus:ring-2 focus:ring-[#003366]/15"
      >
        <option value="">(全部)</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </div>
  );
}

function TextField({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <div className="space-y-1">
      <Label className="text-xs font-semibold text-slate-600">{label}</Label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 placeholder-slate-400 focus:border-[#003366] focus:outline-none focus:ring-2 focus:ring-[#003366]/15"
      />
    </div>
  );
}

function DetailDrawer({ log, onClose }: { log: AuditLogOut; onClose: () => void }) {
  const extraJson = useMemo(
    () => (log.extra ? JSON.stringify(log.extra, null, 2) : "(空)"),
    [log.extra]
  );
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30">
      <div className="h-full w-full max-w-xl overflow-y-auto bg-white p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">审计详情 · #{log.id}</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="h-5 w-5" />
          </button>
        </div>
        <dl className="grid grid-cols-3 gap-y-3 text-sm">
          <Row k="时间" v={formatTime(log.created_at)} />
          <Row k="Trace ID" v={<span className="font-mono text-xs">{log.trace_id}</span>} />
          <Row k="用户" v={log.user_email ?? "—"} />
          <Row k="用户 ID" v={log.user_id ?? "—"} />
          <Row k="资源" v={`${log.resource_type}${log.resource_id ? "/" + log.resource_id : ""}`} />
          <Row k="动作" v={log.action} />
          <Row k="状态" v={<StatusBadge status={log.status} />} />
          <Row k="请求" v={`${log.method ?? "—"} ${log.path ?? ""}`.trim()} />
          <Row k="IP" v={log.ip ?? "—"} />
          {log.error_message && <Row k="错误信息" v={<span className="text-red-600">{log.error_message}</span>} />}
        </dl>
        <div className="mt-6">
          <div className="mb-2 text-sm font-semibold text-slate-700">extra(完整 JSON)</div>
          <pre className="max-h-96 overflow-auto rounded-lg bg-slate-50 p-4 font-mono text-xs text-slate-700">
            {extraJson}
          </pre>
        </div>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <>
      <dt className="col-span-1 text-slate-500">{k}</dt>
      <dd className="col-span-2 text-slate-800">{v}</dd>
    </>
  );
}

export default function Page() {
  return (
    <RouteGuard requiredPermissions={[Permissions.SYSTEM_AUDIT]}>
      <Inner />
    </RouteGuard>
  );
}
