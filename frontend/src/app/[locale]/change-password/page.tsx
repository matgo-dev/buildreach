"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, CheckCircle2, Eye, EyeOff, KeyRound, Loader2 } from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Label } from "@/components/ui/label";
import { authApi } from "@/lib/auth";
import { defaultDashboardOf } from "@/config/navigation";
import { ApiError } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import { validatePassword, validatePasswordConfirm } from "@/lib/validators";

function Inner() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const [oldPwd, setOldPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showOld, setShowOld] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [oldErr, setOldErr] = useState<string | null>(null);
  const [newErr, setNewErr] = useState<string | null>(null);
  const [confirmErr, setConfirmErr] = useState<string | null>(null);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const oe = oldPwd ? null : "请输入旧密码";
    const ne = validatePassword(newPwd);
    const ce = validatePasswordConfirm(newPwd, confirm);
    setOldErr(oe);
    setNewErr(ne);
    setConfirmErr(ce);
    const first = oe ?? ne ?? ce;
    if (first) return setError(first);
    setError("");
    setSubmitting(true);
    try {
      await authApi.changePassword(oldPwd, newPwd);
      const me = await authApi.me();
      setUser(me);
      router.replace(defaultDashboardOf(me.roles));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "修改失败,请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  const matchOk = confirm.length > 0 && newPwd === confirm && !confirmErr;

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-[#003366] to-[#0F4C81] p-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center text-white">
          <div className="mx-auto mb-4 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-white/10 backdrop-blur">
            <KeyRound className="h-7 w-7" />
          </div>
          <h1 className="text-2xl font-bold">修改密码</h1>
          <p className="mt-2 text-sm text-white/60">
            {user?.must_change_password
              ? "首次登录需修改初始密码后才能继续"
              : `当前账号:${user?.email}`}
          </p>
        </div>

        <div className="rounded-2xl border-t-4 border-[#FF6B35] bg-white p-8 shadow-xl">
          {error && (
            <div className="mb-5 flex items-center gap-2.5 rounded-lg border-l-4 border-red-500 bg-red-50 px-4 py-3 text-sm text-red-700">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={onSubmit} className="space-y-4" noValidate>
            <PwdField
              id="oldPwd"
              label="旧密码"
              value={oldPwd}
              onChange={(v) => { setOldPwd(v); if (oldErr) setOldErr(null); }}
              onBlur={() => setOldErr(oldPwd ? null : "请输入旧密码")}
              error={oldErr}
              show={showOld}
              onToggle={() => setShowOld(!showOld)}
            />
            <PwdField
              id="newPwd"
              label="新密码"
              hint="11-50 位,需 3 类字符"
              value={newPwd}
              onChange={(v) => {
                setNewPwd(v);
                if (newErr) setNewErr(null);
                if (confirmErr) setConfirmErr(null);
              }}
              onBlur={() => setNewErr(validatePassword(newPwd))}
              error={newErr}
              show={showNew}
              onToggle={() => setShowNew(!showNew)}
            />
            <div>
              <PwdField
                id="confirm"
                label="确认新密码"
                value={confirm}
                onChange={(v) => { setConfirm(v); if (confirmErr) setConfirmErr(null); }}
                onBlur={() => setConfirmErr(validatePasswordConfirm(newPwd, confirm))}
                error={confirmErr}
                show={showConfirm}
                onToggle={() => setShowConfirm(!showConfirm)}
              />
              {!confirmErr && matchOk && (
                <p className="mt-1 flex items-center gap-1 text-xs text-[#10B981]">
                  <CheckCircle2 className="h-3 w-3" /> 密码匹配
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="mt-2 flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-[#003366] text-base font-semibold text-white shadow-sm transition-all hover:bg-[#002244] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-70"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  提交中...
                </>
              ) : (
                "修改密码"
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

function PwdField({
  id,
  label,
  hint,
  value,
  onChange,
  onBlur,
  error,
  show,
  onToggle,
}: {
  id: string;
  label: string;
  hint?: string;
  value: string;
  onChange: (v: string) => void;
  onBlur?: () => void;
  error?: string | null;
  show: boolean;
  onToggle: () => void;
}) {
  const base =
    "h-11 w-full rounded-lg border bg-white px-3 pr-12 text-sm text-gray-800 placeholder-gray-400 transition-all focus:outline-none focus:ring-2";
  const tone = error
    ? "border-red-400 focus:border-red-500 focus:ring-red-500/15"
    : "border-gray-200 focus:border-[#FF6B35] focus:ring-[#FF6B35]/15";
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-sm font-semibold text-gray-700">
        {label} {hint && <span className="font-normal text-gray-400">({hint})</span>}
      </Label>
      <div className="relative">
        <input
          id={id}
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
          className={`${base} ${tone}`}
        />
        <button
          type="button"
          onClick={onToggle}
          tabIndex={-1}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 transition-colors hover:text-gray-600"
        >
          {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
      {error && (
        <p className="mt-1 flex items-center gap-1 text-xs text-red-500">
          <AlertCircle className="h-3 w-3" /> {error}
        </p>
      )}
    </div>
  );
}

export default function ChangePasswordPage() {
  return (
    <RouteGuard enforceChangePassword={false}>
      <Inner />
    </RouteGuard>
  );
}
