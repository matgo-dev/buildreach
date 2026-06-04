"use client";
import { Users } from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { PermissionPlaceholderPage } from "@/components/layout/PermissionPlaceholderPage";

// /supplier/members:成员管理占位(PRD v1.3 §5.5)。
// 本轮不挂权限点(T-MEMBER 待办时再细化角色与权限)。
export default function Page() {
  return (
    <RouteGuard>
      <PermissionPlaceholderPage
        title="成员管理"
        description="功能即将上线 · owner 可在此邀请、移除企业内员工"
        moduleLabel="SUPPLIER 工作台"
        resource={null}
        requiredPermissions={[]}
        icon={Users}
      />
    </RouteGuard>
  );
}
