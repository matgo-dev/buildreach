"use client";
import { useCallback, useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { AlertCircle, Loader2, Plus, ShieldAlert, X } from "lucide-react";

import { Label } from "@/components/ui/label";
import ConfirmModal from "@/components/ui/ConfirmModal";
import { useToast } from "@/components/ui/Toast";
import { useAuthStore } from "@/stores/authStore";
import { ApiError } from "@/lib/api";
import { orgMembersApi, type MemberOut } from "@/lib/orgMembers";
import { PASSWORD_RULE_MESSAGE, validateEmail, validatePassword, validateRequired } from "@/lib/validators";
import { formatRelativeTime } from "@/lib/formatters";

export default function BuyerMembersPage() {
  const t = useTranslations("buyerMembers");
  const user = useAuthStore((s) => s.user);
  const isOwner = user?.organization?.type === "BUYER_ORG" && user.organization.is_owner;

  if (!isOwner) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white py-16 text-center">
        <ShieldAlert className="h-10 w-10 text-slate-300" />
        <p className="mt-3 text-sm text-muted">{t("ownerOnly")}</p>
      </div>
    );
  }
  return <MembersInner />;
}

function MembersInner() {
  const t = useTranslations("buyerMembers");
  const locale = useLocale();
  const toast = useToast();
  const me = useAuthStore((s) => s.user);
  const [items, setItems] = useState<MemberOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [disableTarget, setDisableTarget] = useState<MemberOut | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setItems(await orgMembersApi.list());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const onDisableConfirm = async () => {
    if (!disableTarget) return;
    const target = disableTarget;
    setBusyId(target.id);
    try {
      await orgMembersApi.disable(target.id);
      setDisableTarget(null);
      await load();
      toast.success(t("toast.disabled", { email: target.email ?? "" }));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : t("toast.disableFailed"));
    } finally {
      setBusyId(null);
    }
  };

  const onEnable = async (m: MemberOut) => {
    setBusyId(m.id);
    try {
      await orgMembersApi.enable(m.id);
      await load();
      toast.success(t("toast.enabled", { email: m.email ?? "" }));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : t("toast.enableFailed"));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-ink">{t("title")}</h1>
          <p className="mt-1 text-sm text-muted">{t("subtitle")}</p>
        </div>
        <button
          onClick={() => setCreateOpen(true)}
          className="flex h-10 items-center gap-2 rounded-lg bg-teal-700 px-4 text-sm font-semibold text-white shadow-sm hover:bg-teal-700/90"
        >
          <Plus className="h-4 w-4" /> {t("create")}
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
              <th className="px-4 py-3 text-left font-semibold">{t("col.name")}</th>
              <th className="px-4 py-3 text-left font-semibold">{t("col.email")}</th>
              <th className="px-4 py-3 text-left font-semibold">{t("col.phone")}</th>
              <th className="px-4 py-3 text-left font-semibold">{t("col.role")}</th>
              <th className="px-4 py-3 text-left font-semibold">{t("col.status")}</th>
              <th className="px-4 py-3 text-left font-semibold">{t("col.joined")}</th>
              <th className="px-4 py-3 text-left font-semibold whitespace-nowrap">{t("col.actions")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-400">
                  <Loader2 className="inline h-4 w-4 animate-spin" /> {t("loading")}
                </td>
              </tr>
            )}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-400">{t("empty")}</td>
              </tr>
            )}
            {!loading &&
              items.map((m) => {
                const isSelf = m.id === me?.id;
                return (
                  <tr key={m.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 text-ink">{m.name}</td>
                    <td className="px-4 py-3 text-slate-700">{m.email ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-600">{m.phone ?? "—"}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          m.is_owner ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-ink"
                        }`}
                      >
                        {t(m.is_owner ? "role.owner" : "role.member")}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                          m.status === "ACTIVE" ? "bg-emerald-50 text-emerald-700" : "bg-slate-200 text-slate-600"
                        }`}
                      >
                        {t(`status.${m.status}`)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-500">{formatRelativeTime(m.created_at, locale)}</td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {!isSelf && !m.is_owner && m.status !== "DEACTIVATED" && (
                        m.status === "ACTIVE" ? (
                          <button
                            disabled={busyId === m.id}
                            onClick={() => setDisableTarget(m)}
                            className="rounded border border-red-300 px-3 py-1 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
                          >
                            {t("actions.disable")}
                          </button>
                        ) : (
                          <button
                            disabled={busyId === m.id}
                            onClick={() => onEnable(m)}
                            className="rounded border border-emerald-300 px-3 py-1 text-xs font-medium text-emerald-600 hover:bg-emerald-50 disabled:opacity-50"
                          >
                            {t("actions.enable")}
                          </button>
                        )
                      )}
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>

      <ConfirmModal
        open={!!disableTarget}
        title={t("actions.disable")}
        description={disableTarget ? t("confirmDisable", { email: disableTarget.email ?? "" }) : ""}
        confirmLabel={t("actions.disable")}
        cancelLabel={t("actions.cancel")}
        variant="danger"
        loading={busyId !== null}
        onConfirm={onDisableConfirm}
        onCancel={() => setDisableTarget(null)}
      />

      {createOpen && (
        <CreateMemberModal
          onClose={() => setCreateOpen(false)}
          onCreated={async () => {
            setCreateOpen(false);
            await load();
            toast.success(t("toast.created"));
          }}
        />
      )}
    </div>
  );
}

function CreateMemberModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => Promise<void> }) {
  const t = useTranslations("buyerMembers");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState("");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (validateRequired(name)) return setErr(t("form.nameRequired"));
    const emailErr = validateEmail(email, {
      required: t("form.emailRequired"),
      format: t("form.emailFormat"),
      domain: t("form.emailDomain"),
    });
    if (emailErr) return setErr(emailErr);
    const pwErr = validatePassword(password);
    if (pwErr) return setErr(pwErr);

    setErr("");
    setSubmitting(true);
    try {
      await orgMembersApi.create({ name: name.trim(), email: email.trim(), password });
      await onCreated();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("toast.createFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  const inputCls =
    "h-10 w-full rounded-lg border border-slate-300 px-3 text-sm text-ink focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-ink">{t("form.title")}</h2>
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
          <div className="space-y-1">
            <Label htmlFor="m-name" className="text-sm font-semibold text-slate-700">{t("form.name")}</Label>
            <input id="m-name" value={name} onChange={(e) => setName(e.target.value)} className={inputCls} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="m-email" className="text-sm font-semibold text-slate-700">{t("form.email")}</Label>
            <input id="m-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} className={inputCls} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="m-password" className="text-sm font-semibold text-slate-700">{t("form.password")}</Label>
            <input id="m-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} className={inputCls} />
            <p className="mt-1 text-xs text-slate-400">{PASSWORD_RULE_MESSAGE}</p>
          </div>
          <p className="text-xs text-muted">{t("form.hint")}</p>
          <div className="mt-5 flex justify-end gap-2">
            <button type="button" onClick={onClose} className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50">
              {t("actions.cancel")}
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="flex h-9 items-center gap-2 rounded-lg bg-teal-700 px-4 text-sm font-semibold text-white hover:bg-teal-700/90 disabled:opacity-60"
            >
              {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
              {t("actions.submit")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
