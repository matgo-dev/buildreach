"use client";
import { useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  AtSign,
  CheckCircle2,
  Eye,
  EyeOff,
  KeyRound,
  Loader2,
  Phone,
  UserRound,
} from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Label } from "@/components/ui/label";
import { authApi } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";

import {
  validateEmail,
  validatePhoneOptional,
  validateUsernameOptional,
} from "@/lib/validators";

function Inner() {
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  if (!user) return null;

  // 顶部条 + 主体
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      <header className="bg-white shadow-sm">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-6 py-4">
          <Link href="/" className="text-sm text-slate-500 hover:text-slate-700">
            ← 返回首页
          </Link>
          <h1 className="text-sm font-semibold text-slate-700">账户设置</h1>
          <span className="w-16" />
        </div>
      </header>

      <main className="mx-auto max-w-3xl space-y-6 px-6 py-8">
        <ProfileCard
          initialName={user.name}
          onSaved={(u) => setUser({ ...user, name: u.name })}
        />
        <EmailCard
          currentEmail={user.email}
          onSaved={(u) => setUser({ ...user, email: u.email })}
        />
        <UsernameCard
          currentUsername={user.username}
          onSaved={(u) => setUser({ ...user, username: u.username })}
        />
        <PhoneCard
          currentPhone={user.phone}
          onSaved={(u) => setUser({ ...user, phone: u.phone })}
        />
        <PasswordCard />
      </main>
    </div>
  );
}

// ---------- 卡片复用 ----------

function SectionCard({
  icon: Icon,
  title,
  desc,
  children,
}: {
  icon: typeof UserRound;
  title: string;
  desc: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#003366]/10">
          <Icon className="h-5 w-5 text-[#003366]" />
        </div>
        <div className="flex-1">
          <h2 className="text-base font-semibold text-slate-900">{title}</h2>
          <p className="mt-0.5 text-sm text-slate-500">{desc}</p>
        </div>
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function Alert({ kind, children }: { kind: "error" | "success"; children: React.ReactNode }) {
  const cls =
    kind === "error"
      ? "border-red-500 bg-red-50 text-red-700"
      : "border-[#10B981] bg-[#10B981]/10 text-[#047857]";
  const Icon = kind === "error" ? AlertCircle : CheckCircle2;
  return (
    <div className={`mb-4 flex items-center gap-2.5 rounded-lg border-l-4 px-4 py-2.5 text-sm ${cls}`}>
      <Icon className="h-4 w-4 shrink-0" />
      <span>{children}</span>
    </div>
  );
}

interface TextInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  hasError?: boolean;
}

function TextInput({ hasError, className, ...rest }: TextInputProps) {
  const base =
    "h-11 w-full rounded-lg border bg-white px-3 text-sm text-gray-800 placeholder-gray-400 transition-all focus:outline-none focus:ring-2";
  const tone = hasError
    ? "border-red-400 focus:border-red-500 focus:ring-red-500/15"
    : "border-gray-200 focus:border-[#FF6B35] focus:ring-[#FF6B35]/15";
  return <input {...rest} className={`${base} ${tone} ${className ?? ""}`} />;
}

function FieldError({ children }: { children: React.ReactNode }) {
  return <p className="text-xs text-red-500">{children}</p>;
}

function PasswordInput({
  value,
  onChange,
  show,
  onToggle,
  ...rest
}: {
  value: string;
  onChange: (v: string) => void;
  show: boolean;
  onToggle: () => void;
} & Omit<React.InputHTMLAttributes<HTMLInputElement>, "value" | "onChange">) {
  return (
    <div className="relative">
      <input
        {...rest}
        type={show ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-11 w-full rounded-lg border border-gray-200 bg-white px-3 pr-12 text-sm text-gray-800 placeholder-gray-400 transition-all focus:border-[#FF6B35] focus:outline-none focus:ring-2 focus:ring-[#FF6B35]/15"
      />
      <button
        type="button"
        onClick={onToggle}
        tabIndex={-1}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
      >
        {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
}

function SubmitButton({ submitting, children }: { submitting: boolean; children: React.ReactNode }) {
  return (
    <button
      type="submit"
      disabled={submitting}
      className="flex h-10 items-center gap-2 rounded-lg bg-[#003366] px-5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-[#002244] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-70"
    >
      {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}

// ---------- 各卡片 ----------

function ProfileCard({
  initialName,
  onSaved,
}: {
  initialName: string;
  onSaved: (u: { name: string }) => void;
}) {
  const [name, setName] = useState(initialName);
  const [nameErr, setNameErr] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const err = name.trim() ? null : "姓名不能为空";
    setNameErr(err);
    if (err) return setError(err);
    setError("");
    setSuccess("");
    setSubmitting(true);
    try {
      const u = await authApi.updateProfile({ name });
      onSaved({ name: u.name });
      setSuccess("已保存");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SectionCard icon={UserRound} title="基础资料" desc="姓名(无需密码)">
      {error && <Alert kind="error">{error}</Alert>}
      {success && <Alert kind="success">{success}</Alert>}
      <form className="space-y-4" onSubmit={onSubmit} noValidate>
        <div className="space-y-1.5">
          <Label htmlFor="name" className="text-sm font-semibold text-gray-700">姓名 *</Label>
          <TextInput
            id="name"
            value={name}
            onChange={(e) => { setName(e.target.value); if (nameErr) setNameErr(null); }}
            onBlur={() => setNameErr(name.trim() ? null : "姓名不能为空")}
            hasError={!!nameErr}
          />
          {nameErr && <FieldError>{nameErr}</FieldError>}
        </div>
        <SubmitButton submitting={submitting}>保存</SubmitButton>
      </form>
    </SectionCard>
  );
}

function PhoneCard({
  currentPhone,
  onSaved,
}: {
  currentPhone: string | null;
  onSaved: (u: { phone: string | null }) => void;
}) {
  const [newPhone, setNewPhone] = useState(currentPhone ?? "");
  const [phoneErr, setPhoneErr] = useState<string | null>(null);
  const [pwd, setPwd] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = newPhone.trim();
    const target = trimmed === "" ? null : trimmed;
    const fmtErr = validatePhoneOptional(trimmed);
    setPhoneErr(fmtErr);
    if (fmtErr) return setError(fmtErr);
    if (target === (currentPhone ?? null)) return setError("新手机号与当前一致");
    if (!pwd) return setError("请输入当前密码");
    setError("");
    setSuccess("");
    setSubmitting(true);
    try {
      const u = await authApi.changePhone(target, pwd);
      onSaved({ phone: u.phone });
      setSuccess(
        target === null
          ? "手机号已清空,后续不能再用手机号登录"
          : `手机号已更新为 ${target}`
      );
      setPwd("");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.status === 401 ? "当前密码错误" : err.message);
      } else {
        setError("保存失败");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SectionCard
      icon={Phone}
      title="登录手机号"
      desc={`当前:${currentPhone ?? "(未设置,不能用手机号登录)"} · 留空清除(需当前密码)`}
    >
      {error && <Alert kind="error">{error}</Alert>}
      {success && <Alert kind="success">{success}</Alert>}
      <form className="space-y-4" onSubmit={onSubmit} noValidate>
        <div className="space-y-1.5">
          <Label htmlFor="newPhone" className="text-sm font-semibold text-gray-700">
            新手机号 <span className="font-normal text-gray-400">(留空 = 清除)</span>
          </Label>
          <TextInput
            id="newPhone"
            inputMode="numeric"
            value={newPhone}
            onChange={(e) => {
              setNewPhone(e.target.value.replace(/\D/g, "").slice(0, 11));
              if (phoneErr) setPhoneErr(null);
            }}
            onBlur={() => setPhoneErr(validatePhoneOptional(newPhone))}
            placeholder="11 位"
            hasError={!!phoneErr}
          />
          {phoneErr && <FieldError>{phoneErr}</FieldError>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="phonePwd" className="text-sm font-semibold text-gray-700">当前密码</Label>
          <PasswordInput
            id="phonePwd"
            value={pwd}
            onChange={setPwd}
            show={showPwd}
            onToggle={() => setShowPwd(!showPwd)}
            autoComplete="current-password"
          />
        </div>
        <SubmitButton submitting={submitting}>更新手机号</SubmitButton>
      </form>
    </SectionCard>
  );
}

function EmailCard({
  currentEmail,
  onSaved,
}: {
  currentEmail: string;
  onSaved: (u: { email: string }) => void;
}) {
  const [newEmail, setNewEmail] = useState("");
  const [emailErr, setEmailErr] = useState<string | null>(null);
  const [pwd, setPwd] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const fmtErr = validateEmail(newEmail);
    setEmailErr(fmtErr);
    if (fmtErr) return setError(fmtErr);
    if (newEmail === currentEmail) return setError("新邮箱与当前一致");
    if (!pwd) return setError("请输入当前密码");
    setError("");
    setSuccess("");
    setSubmitting(true);
    try {
      const u = await authApi.changeEmail(newEmail, pwd);
      onSaved({ email: u.email });
      setSuccess(`邮箱已更新为 ${u.email}`);
      setNewEmail("");
      setPwd("");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.status === 401 ? "当前密码错误" : err.message);
      } else {
        setError("保存失败");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SectionCard
      icon={AtSign}
      title="登录邮箱"
      desc={`当前:${currentEmail}(修改需当前密码二次确认)`}
    >
      {error && <Alert kind="error">{error}</Alert>}
      {success && <Alert kind="success">{success}</Alert>}
      <form className="space-y-4" onSubmit={onSubmit} noValidate>
        <div className="space-y-1.5">
          <Label htmlFor="newEmail" className="text-sm font-semibold text-gray-700">新邮箱</Label>
          <TextInput
            id="newEmail"
            type="email"
            value={newEmail}
            onChange={(e) => { setNewEmail(e.target.value); if (emailErr) setEmailErr(null); }}
            onBlur={() => setEmailErr(validateEmail(newEmail))}
            placeholder="new@email.com"
            autoComplete="email"
            hasError={!!emailErr}
          />
          {emailErr && <FieldError>{emailErr}</FieldError>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="emailPwd" className="text-sm font-semibold text-gray-700">当前密码</Label>
          <PasswordInput
            id="emailPwd"
            value={pwd}
            onChange={setPwd}
            show={showPwd}
            onToggle={() => setShowPwd(!showPwd)}
            autoComplete="current-password"
          />
        </div>
        <SubmitButton submitting={submitting}>更新邮箱</SubmitButton>
      </form>
    </SectionCard>
  );
}

function UsernameCard({
  currentUsername,
  onSaved,
}: {
  currentUsername: string | null;
  onSaved: (u: { username: string | null }) => void;
}) {
  const [newUsername, setNewUsername] = useState(currentUsername ?? "");
  const [unameErr, setUnameErr] = useState<string | null>(null);
  const [pwd, setPwd] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = newUsername.trim();
    const target = trimmed === "" ? null : trimmed;
    const fmtErr = validateUsernameOptional(trimmed);
    setUnameErr(fmtErr);
    if (fmtErr) return setError(fmtErr);
    if (target === (currentUsername ?? null)) return setError("新用户名与当前一致");
    if (!pwd) return setError("请输入当前密码");
    setError("");
    setSuccess("");
    setSubmitting(true);
    try {
      const u = await authApi.changeUsername(target, pwd);
      onSaved({ username: u.username });
      setSuccess(target === null ? "用户名已清空,后续只能用邮箱登录" : `用户名已更新为 ${target}`);
      setPwd("");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.status === 401 ? "当前密码错误" : err.message);
      } else {
        setError("保存失败");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SectionCard
      icon={UserRound}
      title="登录用户名"
      desc={`当前:${currentUsername ?? "(未设置,仅能用邮箱登录)"} · 留空清除(需当前密码)`}
    >
      {error && <Alert kind="error">{error}</Alert>}
      {success && <Alert kind="success">{success}</Alert>}
      <form className="space-y-4" onSubmit={onSubmit} noValidate>
        <div className="space-y-1.5">
          <Label htmlFor="newUsername" className="text-sm font-semibold text-gray-700">
            新用户名 <span className="font-normal text-gray-400">(留空 = 清除)</span>
          </Label>
          <TextInput
            id="newUsername"
            value={newUsername}
            onChange={(e) => { setNewUsername(e.target.value); if (unameErr) setUnameErr(null); }}
            onBlur={() => setUnameErr(validateUsernameOptional(newUsername.trim()))}
            placeholder="如 zhang_san"
            hasError={!!unameErr}
          />
          {unameErr && <FieldError>{unameErr}</FieldError>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="unamePwd" className="text-sm font-semibold text-gray-700">当前密码</Label>
          <PasswordInput
            id="unamePwd"
            value={pwd}
            onChange={setPwd}
            show={showPwd}
            onToggle={() => setShowPwd(!showPwd)}
            autoComplete="current-password"
          />
        </div>
        <SubmitButton submitting={submitting}>更新用户名</SubmitButton>
      </form>
    </SectionCard>
  );
}

function PasswordCard() {
  return (
    <SectionCard
      icon={KeyRound}
      title="登录密码"
      desc="为安全起见,修改密码在独立页面完成"
    >
      <Link
        href="/change-password"
        className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 text-sm font-medium text-slate-700 hover:bg-slate-50"
      >
        前往修改密码 →
      </Link>
    </SectionCard>
  );
}

export default function AccountPage() {
  return (
    <RouteGuard>
      <Inner />
    </RouteGuard>
  );
}
