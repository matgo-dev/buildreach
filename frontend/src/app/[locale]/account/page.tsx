"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import {
  Building2,
  ChevronLeft,
  Eye,
  EyeOff,
  Globe,
  Loader2,
  Lock,
  Mail,
  Pencil,
  Shield,
  User,
} from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/Toast";
import { authApi, type OrganizationInfo } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import { useLocale } from "next-intl";
import {
  validateEmail,
  validateUsernameOptional,
} from "@/lib/validators";

// 国家码配置 — 与注册页一致
const PHONE_REGION_CONFIG = {
  TZ: { dialCode: "+255", flag: "🇹🇿", label: "Tanzania", re: /^\d{9}$/, maxLen: 9 },
  CN: { dialCode: "+86", flag: "🇨🇳", label: "China", re: /^1[3-9]\d{9}$/, maxLen: 11 },
} as const;
type PhoneRegion = keyof typeof PHONE_REGION_CONFIG;

// 侧边栏导航区段定义
const SECTIONS = ["personal", "contact", "security", "organization"] as const;
type SectionId = (typeof SECTIONS)[number];

const SECTION_ICONS: Record<SectionId, typeof User> = {
  personal: User,
  contact: Mail,
  security: Shield,
  organization: Building2,
};

// 角色徽章色
const ROLE_COLORS: Record<string, string> = {
  BUYER: "bg-teal-100 text-teal-800",
  SUPPLIER: "bg-blue-100 text-blue-800",
  OPERATOR: "bg-amber-100 text-amber-800",
  ADMIN: "bg-red-100 text-red-800",
};

// 可编辑字段标识
type EditingField = "name" | "email" | "phone" | "username" | "password" | "org" | null;

function Inner() {
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const t = useTranslations("account");
  const locale = useLocale();
  const toast = useToast();

  const [activeSection, setActiveSection] = useState<SectionId>("personal");
  const [editing, setEditing] = useState<EditingField>(null);
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({});

  // 注销账户弹窗状态
  const [showDeactivateModal, setShowDeactivateModal] = useState(false);
  const [deactivatePassword, setDeactivatePassword] = useState("");
  const [deactivateError, setDeactivateError] = useState("");
  const [deactivating, setDeactivating] = useState(false);

  const handleDeactivate = async () => {
    setDeactivating(true);
    try {
      await authApi.deactivateAccount(deactivatePassword);
      toast.success(t("deactivate_success"));
      // 清除本地 auth 状态，跳转登录页
      setTimeout(() => {
        useAuthStore.getState().clear();
        window.location.href = "/login";
      }, 1000);
    } catch (e) {
      if (e instanceof ApiError && e.code === 40301) {
        setDeactivateError(t("deactivate_err_password"));
      } else {
        // 非密码错误（网络超时、服务器错误等）不应显示密码错误文案
        const msg = e instanceof ApiError ? e.message : t("errors.saveFailed");
        setDeactivateError(msg || t("errors.saveFailed"));
      }
    } finally {
      setDeactivating(false);
    }
  };

  // 滚动监听 scroll-spy
  useEffect(() => {
    const handleScroll = () => {
      const offset = 120;
      for (const id of [...SECTIONS].reverse()) {
        const el = sectionRefs.current[id];
        if (el && el.getBoundingClientRect().top <= offset) {
          setActiveSection(id);
          break;
        }
      }
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollTo = (id: SectionId) => {
    sectionRefs.current[id]?.scrollIntoView({ behavior: "smooth", block: "start" });
    setActiveSection(id);
  };

  const startEditing = useCallback((field: EditingField) => {
    setEditing(field);
  }, []);

  const stopEditing = useCallback(() => {
    setEditing(null);
  }, []);

  if (!user) return null;

  const hasOrg = !!user.organization;
  const visibleSections = hasOrg ? SECTIONS : SECTIONS.filter((s) => s !== "organization");

  return (
    <div className="min-h-screen bg-slate-50">
      {/* 顶栏 */}
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-6 py-3">
          <Link
            href="/"
            className="flex items-center gap-1 text-sm text-slate-500 hover:text-[#0c9468] transition-colors"
          >
            <ChevronLeft className="h-4 w-4" />
            {t("backToHome")}
          </Link>
          <h1 className="ml-auto text-sm font-semibold text-slate-700">{t("title")}</h1>
          <span className="w-20" />
        </div>
      </header>

      <div className="mx-auto flex max-w-6xl gap-8 px-6 py-8">
        {/* 侧边栏 - 桌面端可见 */}
        <aside className="hidden md:block w-56 shrink-0">
          <nav className="sticky top-20 space-y-1">
            {visibleSections.map((id) => {
              const Icon = SECTION_ICONS[id];
              const isActive = activeSection === id;
              return (
                <button
                  key={id}
                  onClick={() => scrollTo(id)}
                  className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                    isActive
                      ? "bg-[#0c9468]/10 text-[#0c9468] font-medium"
                      : "text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {t(`sections.${id}`)}
                </button>
              );
            })}
          </nav>
        </aside>

        {/* 主内容区 */}
        <main className="flex-1 min-w-0 space-y-6">
          {/* Profile Header */}
          <div className="rounded-xl bg-white p-6 shadow-sm border border-slate-100">
            <div className="flex items-center gap-4">
              <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-[#0c9468] text-white text-2xl font-bold">
                {user.name.charAt(0).toUpperCase()}
              </div>
              <div className="min-w-0">
                <h2 className="text-xl font-bold text-slate-900 truncate">{user.name}</h2>
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  {user.roles.map((role) => (
                    <span
                      key={role}
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${ROLE_COLORS[role] ?? "bg-slate-100 text-slate-700"}`}
                    >
                      {t(`roles.${role}`)}
                    </span>
                  ))}
                  {user.organization && (
                    <span className="text-sm text-slate-500">{user.organization.name}</span>
                  )}
                </div>
                <p className="mt-1 text-sm text-slate-500">{user.email}</p>
              </div>
            </div>
          </div>

          {/* Section: Personal Info */}
          <section
            id="personal"
            ref={(el) => { sectionRefs.current.personal = el; }}
            className="scroll-mt-24"
          >
            <SectionCard icon={User} title={t("sections.personal")}>
              <FieldRow
                label={t("fields.name")}
                value={user.name}

                editing={editing === "name"}
                onEdit={() => startEditing("name")}
                editForm={
                  <NameEditForm
                    initialName={user.name}
                    t={t}
                    toast={toast}
                    onSaved={(u) => {
                      setUser({ ...user, name: u.name });
                      stopEditing();
                    }}
                    onCancel={stopEditing}
                  />
                }
              />
              <FieldRow
                label={t("fields.language")}
                value={user.language_preference ?? t("placeholders.notSet")}
                icon={<Globe className="h-4 w-4 text-slate-400" />}
              />
            </SectionCard>
          </section>

          {/* Section: Contact & Login */}
          <section
            id="contact"
            ref={(el) => { sectionRefs.current.contact = el; }}
            className="scroll-mt-24"
          >
            <SectionCard icon={Mail} title={t("sections.contact")}>
              <FieldRow
                label={t("fields.email")}
                value={user.email}

                editing={editing === "email"}
                onEdit={() => startEditing("email")}
                editForm={
                  <EmailEditForm
                    currentEmail={user.email}
                    t={t}
                    toast={toast}
                    onSaved={(u) => {
                      setUser({ ...user, email: u.email });
                      stopEditing();
                    }}
                    onCancel={stopEditing}
                  />
                }
              />
              <FieldRow
                label={t("fields.phone")}
                value={user.phone ?? t("placeholders.notSet")}

                editing={editing === "phone"}
                onEdit={() => startEditing("phone")}
                editForm={
                  <PhoneEditForm
                    currentPhone={user.phone}
                    defaultRegion={locale === "zh" ? "CN" : "TZ"}
                    t={t}
                    toast={toast}
                    onSaved={(u) => {
                      setUser({ ...user, phone: u.phone });
                      stopEditing();
                    }}
                    onCancel={stopEditing}
                  />
                }
              />
              {user.username && (
              <FieldRow
                label={t("fields.username")}
                value={user.username}

                editing={editing === "username"}
                onEdit={() => startEditing("username")}
                editForm={
                  <UsernameEditForm
                    currentUsername={user.username}
                    t={t}
                    toast={toast}
                    onSaved={(u) => {
                      setUser({ ...user, username: u.username });
                      stopEditing();
                    }}
                    onCancel={stopEditing}
                  />
                }
              />
              )}
            </SectionCard>
          </section>

          {/* Section: Security */}
          <section
            id="security"
            ref={(el) => { sectionRefs.current.security = el; }}
            className="scroll-mt-24"
          >
            <SectionCard icon={Shield} title={t("sections.security")}>
              <FieldRow
                label={t("fields.password")}
                value={t("placeholders.passwordMasked")}
                icon={<Lock className="h-4 w-4 text-slate-400" />}

                editing={editing === "password"}
                onEdit={() => startEditing("password")}
                editForm={
                  <PasswordEditForm
                    t={t}
                    toast={toast}
                    onSaved={stopEditing}
                    onCancel={stopEditing}
                  />
                }
              />
              <FieldRow
                label={t("fields.accountStatus")}
                value={
                  <span
                    className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      user.status === "ACTIVE"
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-red-100 text-red-700"
                    }`}
                  >
                    {t(`status.${user.status}`)}
                  </span>
                }
              />
            </SectionCard>

          </section>

          {/* Section: Organization */}
          {hasOrg && (
            <section
              id="organization"
              ref={(el) => { sectionRefs.current.organization = el; }}
              className="scroll-mt-24"
            >
              <SectionCard icon={Building2} title={t("sections.organization")}>
                {editing === "org" ? (
                  <div className="px-6 py-4">
                    <OrgEditForm
                      initialName={user.organization!.name}
                      initialUscc={user.organization!.unified_social_credit_code ?? ""}
                      t={t}
                      toast={toast}
                      onSaved={(org) => {
                        setUser({ ...user, organization: org });
                        stopEditing();
                      }}
                      onCancel={stopEditing}
                    />
                  </div>
                ) : (
                  <>
                    {/* 仅买方组织 owner 可编辑名称/统一社会信用代码;供应商组织与非 owner 只读 */}
                    <FieldRow
                      label={t("fields.orgName")}
                      value={user.organization!.name || t("placeholders.notSet")}
                      onEdit={
                        user.organization!.type === "BUYER_ORG" && user.organization!.is_owner
                          ? () => startEditing("org")
                          : undefined
                      }
                    />
                    {user.organization!.type === "BUYER_ORG" && (
                      <FieldRow
                        label={t("fields.orgUscc")}
                        value={user.organization!.unified_social_credit_code || t("placeholders.notSet")}
                        onEdit={user.organization!.is_owner ? () => startEditing("org") : undefined}
                      />
                    )}
                  </>
                )}
                <FieldRow
                  label={t("fields.orgType")}
                  value={t(`orgTypes.${user.organization!.type}`)}
                />
                <FieldRow
                  label={t("fields.orgRole")}
                  value={
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        user.organization!.is_owner
                          ? "bg-amber-100 text-amber-800"
                          : "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {t(`orgRoles.${user.organization!.is_owner ? "owner" : "member"}`)}
                    </span>
                  }
                />
                {user.organization!.status && (
                  <FieldRow
                    label={t("fields.orgStatus")}
                    value={user.organization!.status}
                  />
                )}
              </SectionCard>
            </section>
          )}

          {/* 危险区域：注销账户 */}
          <div className="mt-8 rounded-xl border border-red-200 bg-red-50/50 px-6 py-5">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-red-700">{t("deactivate_title")}</h3>
                <p className="mt-1 text-xs text-red-500/80">{t("deactivate_warning")}</p>
              </div>
              <button
                onClick={() => setShowDeactivateModal(true)}
                className="shrink-0 rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-600 transition-colors hover:bg-red-50 hover:border-red-400"
              >
                {t("deactivate_button")}
              </button>
            </div>
          </div>

          {/* 注销确认弹窗 */}
          {showDeactivateModal && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
              <div className="bg-white rounded-xl p-6 w-full max-w-sm mx-4 shadow-xl">
                <h3 className="text-lg font-semibold text-gray-900">{t("deactivate_title")}</h3>
                <p className="text-sm text-gray-500 mt-2">{t("deactivate_warning")}</p>
                <div className="mt-4">
                  <PasswordField
                    value={deactivatePassword}
                    onChange={(v) => { setDeactivatePassword(v); setDeactivateError(""); }}
                    placeholder={t("deactivate_password_label")}
                  />
                </div>
                {deactivateError && (
                  <p className="text-xs text-red-500 mt-1">{deactivateError}</p>
                )}
                <div className="flex gap-3 mt-6">
                  <button
                    onClick={() => {
                      setShowDeactivateModal(false);
                      setDeactivatePassword("");
                      setDeactivateError("");
                    }}
                    className="flex-1 h-9 px-4 text-sm border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50 transition-colors"
                  >
                    {t("deactivate_cancel")}
                  </button>
                  <button
                    onClick={handleDeactivate}
                    disabled={!deactivatePassword || deactivating}
                    className="flex h-9 flex-1 items-center justify-center gap-1.5 px-4 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {deactivating && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                    {t("deactivate_confirm")}
                  </button>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

// ---------- 通用子组件 ----------

function SectionCard({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof User;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl bg-white shadow-sm border border-slate-100 overflow-hidden">
      <div className="flex items-center gap-2.5 border-b border-slate-100 px-6 py-4">
        <Icon className="h-5 w-5 text-[#0c9468]" />
        <h3 className="text-base font-semibold text-slate-900">{title}</h3>
      </div>
      <div className="divide-y divide-slate-100">{children}</div>
    </div>
  );
}

function FieldRow({
  label,
  value,
  icon,
  editing,
  onEdit,
  editForm,
}: {
  label: string;
  value: React.ReactNode;
  icon?: React.ReactNode;
  editing?: boolean;
  onEdit?: () => void;
  editForm?: React.ReactNode;
}) {
  const editable = !!onEdit && !editing;
  return (
    <div className="px-6 py-4">
      {editing ? (
        <div>
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-3">{label}</p>
          {editForm}
        </div>
      ) : (
        <div
          onClick={editable ? onEdit : undefined}
          className={`flex items-center gap-3 min-w-0 rounded-lg -mx-2 px-2 py-1.5 ${
            editable ? "cursor-pointer group hover:bg-slate-50 transition-colors" : ""
          }`}
        >
          {icon}
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">{label}</p>
            <div className="mt-0.5 text-sm text-slate-900 truncate">{value}</div>
          </div>
          {editable && (
            <Pencil className="h-3.5 w-3.5 text-slate-300 group-hover:text-[#0c9468] transition-colors shrink-0" />
          )}
        </div>
      )}
    </div>
  );
}

function InlineInput({
  hasError,
  className: _,
  ...rest
}: React.InputHTMLAttributes<HTMLInputElement> & { hasError?: boolean }) {
  return (
    <input
      {...rest}
      className={`h-10 w-full rounded-lg border bg-white px-3 text-sm text-slate-800 placeholder-slate-400 transition-all focus:outline-none focus:ring-2 ${
        hasError
          ? "border-red-400 focus:border-red-500 focus:ring-red-500/15"
          : "border-slate-200 focus:border-[#0c9468] focus:ring-[#0c9468]/15"
      }`}
    />
  );
}

function PasswordField({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <input
        type={show ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete="current-password"
        className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 pr-10 text-sm text-slate-800 placeholder-slate-400 transition-all focus:border-[#0c9468] focus:outline-none focus:ring-2 focus:ring-[#0c9468]/15"
      />
      <button
        type="button"
        onClick={() => setShow(!show)}
        tabIndex={-1}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
      >
        {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
}

// ---------- 各字段编辑表单 ----------

type TranslateFunc = ReturnType<typeof useTranslations<"account">>;
type Toast = ReturnType<typeof useToast>;

function NameEditForm({
  initialName,
  t,
  toast,
  onSaved,
  onCancel,
}: {
  initialName: string;
  t: TranslateFunc;
  toast: Toast;
  onSaved: (u: { name: string }) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initialName);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError(t("errors.nameRequired"));
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      const u = await authApi.updateProfile({ name: name.trim() });
      toast.success(t("success.nameSaved"));
      onSaved({ name: u.name });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : t("errors.saveFailed");
      setError(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-3 max-w-md">
      <div>
        <Label htmlFor="editName" className="text-xs text-slate-500">{t("fields.name")}</Label>
        <InlineInput
          id="editName"
          value={name}
          onChange={(e) => { setName(e.target.value); setError(""); }}
          placeholder={t("placeholders.enterName")}
          hasError={!!error}
        />
        {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
      </div>
      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="flex h-9 items-center gap-1.5 rounded-lg bg-[#0c9468] px-4 text-sm font-medium text-white shadow-sm transition-all hover:bg-[#0c9468]/90 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {t("actions.save")}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="h-9 rounded-lg px-4 text-sm font-medium text-slate-600 hover:bg-slate-100 transition-colors"
        >
          {t("actions.cancel")}
        </button>
      </div>
    </form>
  );
}

function OrgEditForm({
  initialName,
  initialUscc,
  t,
  toast,
  onSaved,
  onCancel,
}: {
  initialName: string;
  initialUscc: string;
  t: TranslateFunc;
  toast: Toast;
  onSaved: (org: OrganizationInfo) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initialName);
  const [uscc, setUscc] = useState(initialUscc);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError(t("errors.orgNameRequired"));
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      // uscc 传空串 = 清空(后端 PATCH 语义)
      const org = await authApi.updateOrganization({
        name: name.trim(),
        unified_social_credit_code: uscc.trim(),
      });
      toast.success(t("success.orgSaved"));
      onSaved(org);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : t("errors.saveFailed");
      setError(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-3 max-w-md">
      <div>
        <Label htmlFor="editOrgName" className="text-xs text-slate-500">{t("fields.orgName")}</Label>
        <InlineInput
          id="editOrgName"
          value={name}
          onChange={(e) => { setName(e.target.value); setError(""); }}
          placeholder={t("placeholders.enterOrgName")}
          hasError={!!error}
        />
      </div>
      <div>
        <Label htmlFor="editOrgUscc" className="text-xs text-slate-500">{t("fields.orgUscc")}</Label>
        <InlineInput
          id="editOrgUscc"
          value={uscc}
          onChange={(e) => setUscc(e.target.value)}
          placeholder={t("placeholders.enterUscc")}
          maxLength={18}
        />
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}
      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="flex h-9 items-center gap-1.5 rounded-lg bg-[#0c9468] px-4 text-sm font-medium text-white shadow-sm transition-all hover:bg-[#0c9468]/90 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {t("actions.save")}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="h-9 rounded-lg px-4 text-sm font-medium text-slate-600 hover:bg-slate-100 transition-colors"
        >
          {t("actions.cancel")}
        </button>
      </div>
    </form>
  );
}

function EmailEditForm({
  currentEmail,
  t,
  toast,
  onSaved,
  onCancel,
}: {
  currentEmail: string;
  t: TranslateFunc;
  toast: Toast;
  onSaved: (u: { email: string }) => void;
  onCancel: () => void;
}) {
  const tc = useTranslations("common");
  const [newEmail, setNewEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const fmtErr = validateEmail(newEmail, {
      required: tc("err_email_required"),
      format: tc("err_email_format"),
      domain: tc("err_email_domain"),
    });
    if (fmtErr) { setError(fmtErr); return; }
    if (newEmail === currentEmail) { setError(t("errors.sameAsCurrentEmail")); return; }
    setError("");
    setSubmitting(true);
    try {
      const u = await authApi.updateProfile({ email: newEmail });
      toast.success(t("success.emailSaved"));
      onSaved({ email: u.email });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : t("errors.saveFailed");
      setError(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-3 max-w-md">
      <div>
        <Label htmlFor="editEmail" className="text-xs text-slate-500">{t("fields.email")}</Label>
        <InlineInput
          id="editEmail"
          type="email"
          value={newEmail}
          onChange={(e) => { setNewEmail(e.target.value); setError(""); }}
          placeholder={t("placeholders.enterNewEmail")}
          autoComplete="email"
        />
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}
      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="flex h-9 items-center gap-1.5 rounded-lg bg-[#0c9468] px-4 text-sm font-medium text-white shadow-sm transition-all hover:bg-[#0c9468]/90 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {t("actions.save")}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="h-9 rounded-lg px-4 text-sm font-medium text-slate-600 hover:bg-slate-100 transition-colors"
        >
          {t("actions.cancel")}
        </button>
      </div>
    </form>
  );
}

function PhoneEditForm({
  currentPhone,
  defaultRegion,
  t,
  toast,
  onSaved,
  onCancel,
}: {
  currentPhone: string | null;
  defaultRegion: PhoneRegion;
  t: TranslateFunc;
  toast: Toast;
  onSaved: (u: { phone: string | null }) => void;
  onCancel: () => void;
}) {
  const [region, setRegion] = useState<PhoneRegion>(defaultRegion);
  const [newPhone, setNewPhone] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const cfg = PHONE_REGION_CONFIG[region];

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = newPhone.trim();
    const target = trimmed === "" ? null : trimmed;
    if (trimmed && !cfg.re.test(trimmed)) {
      setError(t("errors.invalidPhone"));
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      const u = await authApi.updateProfile({
        phone: target,
        phone_region: target ? region : undefined,
      });
      toast.success(target === null ? t("success.phoneCleared") : t("success.phoneSaved"));
      onSaved({ phone: u.phone });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : t("errors.saveFailed");
      setError(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-3 max-w-md">
      <p className="text-xs text-slate-500">{t("hints.phoneCanBeCleared")}</p>
      <div>
        <Label htmlFor="editPhone" className="text-xs text-slate-500">{t("fields.phone")}</Label>
        <div className="flex">
          <select
            value={region}
            onChange={(e) => { setRegion(e.target.value as PhoneRegion); setNewPhone(""); setError(""); }}
            className="h-10 rounded-l-lg border border-r-0 border-slate-200 bg-slate-50 px-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#0c9468]/15"
          >
            {(Object.keys(PHONE_REGION_CONFIG) as PhoneRegion[]).map((r) => (
              <option key={r} value={r}>
                {PHONE_REGION_CONFIG[r].flag} {PHONE_REGION_CONFIG[r].dialCode}
              </option>
            ))}
          </select>
          <input
            id="editPhone"
            inputMode="numeric"
            value={newPhone}
            onChange={(e) => {
              setNewPhone(e.target.value.replace(/\D/g, "").slice(0, cfg.maxLen));
              setError("");
            }}
            placeholder={t("placeholders.enterNewPhone")}
            className={`h-10 flex-1 rounded-r-lg border bg-white px-3 text-sm text-slate-800 placeholder-slate-400 transition-all focus:outline-none focus:ring-2 ${
              error
                ? "border-red-400 focus:border-red-500 focus:ring-red-500/15"
                : "border-slate-200 focus:border-[#0c9468] focus:ring-[#0c9468]/15"
            }`}
          />
        </div>
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}
      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="flex h-9 items-center gap-1.5 rounded-lg bg-[#0c9468] px-4 text-sm font-medium text-white shadow-sm transition-all hover:bg-[#0c9468]/90 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {t("actions.save")}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="h-9 rounded-lg px-4 text-sm font-medium text-slate-600 hover:bg-slate-100 transition-colors"
        >
          {t("actions.cancel")}
        </button>
      </div>
    </form>
  );
}

function UsernameEditForm({
  currentUsername,
  t,
  toast,
  onSaved,
  onCancel,
}: {
  currentUsername: string | null;
  t: TranslateFunc;
  toast: Toast;
  onSaved: (u: { username: string | null }) => void;
  onCancel: () => void;
}) {
  const [newUsername, setNewUsername] = useState(currentUsername ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = newUsername.trim();
    const target = trimmed === "" ? null : trimmed;
    const fmtErr = validateUsernameOptional(trimmed);
    if (fmtErr) { setError(fmtErr); return; }
    if (target === (currentUsername ?? null)) { setError(t("errors.sameAsCurrentUsername")); return; }
    setError("");
    setSubmitting(true);
    try {
      const u = await authApi.updateProfile({ username: target });
      toast.success(target === null ? t("success.usernameCleared") : t("success.usernameSaved"));
      onSaved({ username: u.username });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : t("errors.saveFailed");
      setError(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-3 max-w-md">
      <p className="text-xs text-slate-500">{t("hints.usernameCanBeCleared")}</p>
      <div>
        <Label htmlFor="editUsername" className="text-xs text-slate-500">{t("fields.username")}</Label>
        <InlineInput
          id="editUsername"
          value={newUsername}
          onChange={(e) => { setNewUsername(e.target.value); setError(""); }}
          placeholder={t("placeholders.enterNewUsername")}
        />
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}
      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="flex h-9 items-center gap-1.5 rounded-lg bg-[#0c9468] px-4 text-sm font-medium text-white shadow-sm transition-all hover:bg-[#0c9468]/90 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {t("actions.save")}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="h-9 rounded-lg px-4 text-sm font-medium text-slate-600 hover:bg-slate-100 transition-colors"
        >
          {t("actions.cancel")}
        </button>
      </div>
    </form>
  );
}

function PasswordEditForm({
  t,
  toast,
  onSaved,
  onCancel,
}: {
  t: TranslateFunc;
  toast: Toast;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [oldPwd, setOldPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!oldPwd) { setError(t("errors.passwordRequired")); return; }
    if (!newPwd) { setError(t("errors.newPasswordRequired")); return; }
    if (newPwd.length < 8) { setError(t("errors.passwordTooShort")); return; }
    if (newPwd !== confirmPwd) { setError(t("errors.passwordMismatch")); return; }
    setError("");
    setSubmitting(true);
    try {
      await authApi.changePassword(oldPwd, newPwd);
      toast.success(t("success.passwordSavedRedirect"));
      // 后端 token_version+1，当前会话已失效，延迟跳转登录页
      setTimeout(() => {
        useAuthStore.getState().clear();
        window.location.href = "/login";
      }, 1500);
    } catch (err) {
      if (err instanceof ApiError) {
        const msg = err.status === 401 ? t("errors.wrongPassword") : err.message;
        setError(msg);
        toast.error(msg);
      } else {
        setError(t("errors.saveFailed"));
        toast.error(t("errors.saveFailed"));
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-3 max-w-md">
      <div>
        <Label htmlFor="oldPwd" className="text-xs text-slate-500">{t("fields.currentPassword")}</Label>
        <PasswordField value={oldPwd} onChange={(v) => { setOldPwd(v); setError(""); }} placeholder={t("placeholders.enterCurrentPassword")} />
      </div>
      <div>
        <Label htmlFor="newPwd" className="text-xs text-slate-500">{t("fields.newPassword")}</Label>
        <PasswordField value={newPwd} onChange={(v) => { setNewPwd(v); setError(""); }} placeholder={t("placeholders.enterNewPassword")} />
      </div>
      <div>
        <Label htmlFor="confirmPwd" className="text-xs text-slate-500">{t("fields.confirmPassword")}</Label>
        <PasswordField value={confirmPwd} onChange={(v) => { setConfirmPwd(v); setError(""); }} placeholder={t("placeholders.confirmNewPassword")} />
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}
      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="flex h-9 items-center gap-1.5 rounded-lg bg-[#0c9468] px-4 text-sm font-medium text-white shadow-sm transition-all hover:bg-[#0c9468]/90 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {t("actions.save")}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="h-9 rounded-lg px-4 text-sm font-medium text-slate-600 hover:bg-slate-100 transition-colors"
        >
          {t("actions.cancel")}
        </button>
      </div>
    </form>
  );
}

// ---------- 导出 ----------

export default function AccountPage() {
  return (
    <RouteGuard>
      <Inner />
    </RouteGuard>
  );
}
