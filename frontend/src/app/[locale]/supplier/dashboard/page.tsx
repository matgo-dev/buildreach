"use client";
import { AlertCircle } from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { PermissionPlaceholderPage } from "@/components/layout/PermissionPlaceholderPage";
import { useAuthStore } from "@/stores/authStore";
import { STATUS_DRAFT } from "@/config/country-registration-rules";

function DraftBanner() {
  return (
    <div className="mb-4 flex items-start gap-3 rounded-lg border-l-4 border-[#FF6B35] bg-[#FF6B35]/10 px-4 py-3 text-sm text-[#9C3E16]">
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-[#FF6B35]" />
      <div>
        <p className="font-semibold text-[#7A2F11]">入驻申请已提交,资料待完善</p>
        <p className="mt-1 leading-relaxed">
          您的账号已创建,但企业入驻尚未完成审核与资料完善,
          <strong className="font-semibold">暂无法上架商品</strong>。完整入驻流程将在后续版本上线。
        </p>
      </div>
    </div>
  );
}

export default function Page() {
  const org = useAuthStore((s) => s.user?.organization);
  const showBanner = org?.status === STATUS_DRAFT;

  return (
    <RouteGuard>
      {showBanner && <DraftBanner />}
      <PermissionPlaceholderPage />
    </RouteGuard>
  );
}
