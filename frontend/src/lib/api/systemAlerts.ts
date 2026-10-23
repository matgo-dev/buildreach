// 运营端系统告警(外部依赖故障横幅)客户端
//
// 后端契约见 backend/app/api/v1/operator_system_alerts.py;只给 OPERATOR/ADMIN。

import { api } from "../api";

export interface SystemAlertItem {
  /** 目前只有 translation_down;以后邮件/OSS 故障往这里加 kind */
  kind: "translation_down" | string;
  since: string | null;
  /** 提供方错误原文,如 `403 userRateLimitExceeded` */
  detail: string | null;
  pending_rows: number;
}

export const systemAlertsApi = {
  list: () => api.get<{ items: SystemAlertItem[] }>("/api/v1/operator/system-alerts"),
};
