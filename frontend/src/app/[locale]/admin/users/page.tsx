"use client";
import { useCallback, useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, Loader2, Plus, X } from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { adminUsersApi, type AdminUserOut, type InternalRole } from "@/lib/adminUsers";
import { Permissions } from "@/lib/permissions";
import {
  validateEmail,
  validatePassword,
  validateRequired,
  validateUsernameOptional,
} from "@/lib/validators";

const PAGE_SIZE = 20;

function Inner() {
  const [items, setItems] = useState<AdminUserOut[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [toast, setToast] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const load = useCallback(async (p = 1) => {
    setLoading(true);
    setError("");
    try {
      const data = await adminUsersApi.list(p, PAGE_SIZE);
      setItems(data.items);
      setTotal(data.total);
      setPage(p);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(1);
  }, [load]);

  const showToast = (kind: "ok" | "err", text: string) => {
    setToast({ kind, text });
    setTimeout(() => setToast(null), 3000);
  };

  const onDisable = async (u: AdminUserOut) => {
    if (!confirm(`确定停用账号 ${u.email}?\n停用后该用户立即无法登录。`)) return;
    setBusyId(u.id);
    try {
      await adminUsersApi.disable(u.id);
      await load(page);
      showToast("ok", `已停用 ${u.email}`);
    } catch (e) {
      showToast("err", e instanceof ApiError ? e.message : "停用失败");
    } finally {
      setBusyId(null);
    }
  };

  const onEnable = async (u: AdminUserOut) => {
    setBusyId(u.id);
    try {
      await adminUsersApi.enable(u.id);
      await load(page);
      showToast("ok", `已启用 ${u.email}`);
    } catch (e) {
      showToast("err", e instanceof ApiError ? e.message : "启用失败");
    } finally {
      setBusyId(null);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">内部账号管理</h1>
          <p className="mt-1 text-sm text-slate-500">
            创建 / 停用 / 启用 ADMIN 与 OPERATOR 账号。BUYER / SUPPLIER 走自助注册,不在此处创建。
          </p>
        </div>
        <button
          onClick={() => setCreateOpen(true)}
          className="flex h-10 items-center gap-2 rounded-lg bg-[#003366] px-4 text-sm font-semibold text-white shadow-sm hover:bg-[#002244]"
        >
          <Plus className="h-4 w-4" /> 新建账号
        </button>
      </header>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border-l-4 border-red-500 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-4 py-3 text-left font-semibold">ID</th>
              <th className="px-4 py-3 text-left font-semibold">邮箱</th>
              <th className="px-4 py-3 text-left font-semibold">用户名</th>
              <th className="px-4 py-3 text-left font-semibold">姓名</th>
              <th className="px-4 py-3 text-left font-semibold">角色</th>
              <th className="px-4 py-3 text-left font-semibold">状态</th>
              <th className="px-4 py-3 text-left font-semibold">操作</th>
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
                  暂无账号
                </td>
              </tr>
            )}
            {!loading &&
              items.map((u) => (
                <tr key={u.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">#{u.id}</td>
                  <td className="px-4 py-3 text-slate-800">{u.email}</td>
                  <td className="px-4 py-3 text-slate-600">{u.username ?? "—"}</td>
                  <td className="px-4 py-3 text-slate-700">{u.name}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {u.roles.map((r) => (
                        <span
                          key={r}
                          className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700"
                        >
                          {r}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={u.status} />
                  </td>
                  <td className="px-4 py-3">
                    {u.status === "ACTIVE" ? (
                      <button
                        disabled={busyId === u.id}
                        onClick={() => onDisable(u)}
                        className="rounded border border-red-300 px-3 py-1 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
                      >
                        停用
                      </button>
                    ) : (
                      <button
                        disabled={busyId === u.id}
                        onClick={() => onEnable(u)}
                        className="rounded border border-emerald-300 px-3 py-1 text-xs font-medium text-emerald-600 hover:bg-emerald-50 disabled:opacity-50"
                      >
                        启用
                      </button>
                    )}
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

      {toast && (
        <div
          className={
            "fixed bottom-6 right-6 flex items-center gap-2 rounded-lg px-4 py-3 text-sm shadow-lg " +
            (toast.kind === "ok"
              ? "bg-emerald-600 text-white"
              : "bg-red-600 text-white")
          }
        >
          {toast.kind === "ok" ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
          {toast.text}
        </div>
      )}

      {createOpen && (
        <CreateModal
          onClose={() => setCreateOpen(false)}
          onCreated={async () => {
            setCreateOpen(false);
            await load(1);
            showToast("ok", "账号已创建");
          }}
        />
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: "ACTIVE" | "DISABLED" }) {
  const ok = status === "ACTIVE";
  return (
    <span
      className={
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium " +
        (ok ? "bg-emerald-50 text-emerald-700" : "bg-slate-200 text-slate-600")
      }
    >
      <span className={"h-1.5 w-1.5 rounded-full " + (ok ? "bg-emerald-500" : "bg-slate-400")} />
      {ok ? "正常" : "已停用"}
    </span>
  );
}

function CreateModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => Promise<void>;
}) {
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<InternalRole>("OPERATOR");
  const [mustChange, setMustChange] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState("");

  type Field = "email" | "username" | "name" | "password";
  const [fieldErr, setFieldErr] = useState<Partial<Record<Field, string | null>>>({});

  const valueOf = (f: Field): string =>
    ({ email, username, name, password }[f]);

  const runValidator = (f: Field, v: string): string | null => {
    switch (f) {
      case "email": return validateEmail(v);
      case "username": return validateUsernameOptional(v);
      case "name": return validateRequired(v, "姓名");
      case "password": return validatePassword(v);
    }
  };

  const blurOf = (f: Field) => () =>
    setFieldErr((s) => ({ ...s, [f]: runValidator(f, valueOf(f)) }));

  const clear = (f: Field) => {
    if (fieldErr[f]) setFieldErr((s) => ({ ...s, [f]: null }));
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const all: Partial<Record<Field, string | null>> = {
      email: validateEmail(email),
      username: validateUsernameOptional(username),
      name: validateRequired(name, "姓名"),
      password: validatePassword(password),
    };
    setFieldErr(all);
    const first = (Object.values(all).find((x) => x) as string | undefined) ?? "";
    if (first) return setErr(first);
    setErr("");
    setSubmitting(true);
    try {
      await adminUsersApi.create({
        email,
        username: username || undefined,
        name,
        password,
        role,
        must_change_password: mustChange,
      });
      await onCreated();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "创建失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">新建内部账号</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="h-5 w-5" />
          </button>
        </div>
        {err && (
          <div className="mb-3 flex items-center gap-2 rounded-md border-l-4 border-red-500 bg-red-50 px-3 py-2 text-sm text-red-700">
            <AlertCircle className="h-4 w-4" /> {err}
          </div>
        )}
        <form onSubmit={onSubmit} className="space-y-3" noValidate>
          <Field id="email" label="邮箱 *">
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => { setEmail(e.target.value); clear("email"); }}
              onBlur={blurOf("email")}
              className={inputCls(!!fieldErr.email)}
            />
            {fieldErr.email && <p className="mt-1 text-xs text-red-500">{fieldErr.email}</p>}
          </Field>
          <Field id="username" label="用户名(选填)">
            <input
              id="username"
              value={username}
              onChange={(e) => { setUsername(e.target.value); clear("username"); }}
              onBlur={blurOf("username")}
              className={inputCls(!!fieldErr.username)}
            />
            {fieldErr.username && <p className="mt-1 text-xs text-red-500">{fieldErr.username}</p>}
          </Field>
          <Field id="name" label="姓名 *">
            <input
              id="name"
              value={name}
              onChange={(e) => { setName(e.target.value); clear("name"); }}
              onBlur={blurOf("name")}
              className={inputCls(!!fieldErr.name)}
            />
            {fieldErr.name && <p className="mt-1 text-xs text-red-500">{fieldErr.name}</p>}
          </Field>
          <Field id="password" label="初始密码 *">
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => { setPassword(e.target.value); clear("password"); }}
              onBlur={blurOf("password")}
              className={inputCls(!!fieldErr.password)}
            />
            {fieldErr.password ? (
              <p className="mt-1 text-xs text-red-500">{fieldErr.password}</p>
            ) : (
              <p className="mt-1 text-xs text-slate-400">11-50 位,需包含数字、大写字母、小写字母、特殊字符中至少 3 类</p>
            )}
          </Field>
          <Field id="role" label="角色 *">
            <div className="flex gap-3">
              {(["ADMIN", "OPERATOR"] as const).map((r) => (
                <label key={r} className="inline-flex items-center gap-1.5 text-sm">
                  <input
                    type="radio"
                    name="role"
                    value={r}
                    checked={role === r}
                    onChange={() => setRole(r)}
                  />
                  {r}
                </label>
              ))}
            </div>
          </Field>
          <label className="inline-flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={mustChange}
              onChange={(e) => setMustChange(e.target.checked)}
            />
            首次登录强制改密
          </label>
          <div className="mt-5 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="flex h-9 items-center gap-2 rounded-lg bg-[#003366] px-4 text-sm font-semibold text-white hover:bg-[#002244] disabled:opacity-60"
            >
              {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
              创建
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function inputCls(hasError: boolean): string {
  const base =
    "h-10 w-full rounded-lg border bg-white px-3 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2";
  return hasError
    ? `${base} border-red-400 focus:border-red-500 focus:ring-red-500/15`
    : `${base} border-slate-200 focus:border-[#003366] focus:ring-[#003366]/15`;
}

function Field({ id, label, children }: { id: string; label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <Label htmlFor={id} className="text-sm font-semibold text-slate-700">
        {label}
      </Label>
      {children}
    </div>
  );
}

export default function Page() {
  return (
    <RouteGuard requiredPermissions={[Permissions.USER_MANAGE]}>
      <Inner />
    </RouteGuard>
  );
}
