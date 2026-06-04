// 权限点常量 — 实际定义在 config/permission-matrix.ts(单一可信源)。
// 这里 re-export 让旧代码导入路径继续可用。

export { Permissions } from "@/config/permission-matrix";
export type { PermissionCode } from "@/config/permission-matrix";
