"use client";
import { Shield, ShieldAlert, ShieldX } from "lucide-react";

import type { CertificationOut } from "@/lib/api/credit";

// PRD §8.2 只规定证书 status 的颜色(有效绿/过期灰/可疑红);
// 证书类型分组标题统一用中性色,不额外上色避免视觉干扰
const TYPE_META: Record<CertificationOut["cert_type"], { label: string }> = {
  mandatory_country: { label: "目标国强制" },
  system_general: { label: "通用体系" },
  industry_specific: { label: "行业专项" },
};

function _statusVisual(status: CertificationOut["status"], expiresAt: string | null) {
  const today = new Date();
  const expired =
    status === "expired" ||
    (status === "valid" && expiresAt && new Date(expiresAt) < today);
  if (status === "suspicious_forged") {
    return {
      icon: ShieldX,
      bg: "bg-red-50",
      text: "text-red-600",
      border: "border-red-200",
      label: "可疑",
    };
  }
  if (expired) {
    return {
      icon: ShieldAlert,
      bg: "bg-slate-100",
      text: "text-slate-400",
      border: "border-slate-200",
      label: "过期",
    };
  }
  return {
    icon: Shield,
    bg: "bg-emerald-50",
    text: "text-emerald-700",
    border: "border-emerald-200",
    label: "有效",
  };
}

export function CertificationChips({
  certifications,
}: {
  certifications: CertificationOut[];
}) {
  if (certifications.length === 0) {
    return (
      <div className="text-sm text-slate-400">暂无证书数据</div>
    );
  }

  // 按类型分组展示
  const grouped: Record<string, CertificationOut[]> = {};
  for (const c of certifications) {
    (grouped[c.cert_type] ||= []).push(c);
  }

  return (
    <div className="space-y-3">
      {(Object.keys(TYPE_META) as Array<CertificationOut["cert_type"]>)
        .filter((t) => grouped[t])
        .map((t) => (
          <div key={t}>
            <div className="mb-1.5 text-xs font-medium tracking-wide text-slate-600">
              {TYPE_META[t].label}
            </div>
            <div className="flex flex-wrap gap-2">
              {grouped[t].map((c) => {
                const v = _statusVisual(c.status, c.expires_at);
                const Icon = v.icon;
                return (
                  <div
                    key={c.id}
                    className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs ${v.bg} ${v.text} ${v.border}`}
                    title={
                      [
                        c.issuer ? `颁发:${c.issuer}` : "",
                        c.issued_at ? `签发:${c.issued_at}` : "",
                        c.expires_at ? `到期:${c.expires_at}` : "",
                      ]
                        .filter(Boolean)
                        .join(" · ") || undefined
                    }
                  >
                    <Icon className="h-3 w-3" />
                    <span className="font-medium">{c.cert_name}</span>
                    <span className="text-[10px] opacity-70">· {v.label}</span>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
    </div>
  );
}
