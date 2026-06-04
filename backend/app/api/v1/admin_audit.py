"""审计日志查询路由 /api/v1/admin/audit-logs(SYSTEM_AUDIT 权限)。

设计原则:
- 全只读,GET 不写审计(方案 §6.3)
- 时间字段 created_at 走 naive UTC,响应输出 ISO 字符串不带 Z(留前端转)
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.constants import AuditAction, AuditResourceType
from app.core.dependencies import CurrentUser
from app.core.exceptions import NotFoundError, success
from app.db.models.audit_log import AuditLog, AuditStatus
from app.db.session import get_db
from app.rbac.constants import Permissions
from app.rbac.guards import require_permission
from app.services import audit_query_service

router = APIRouter(prefix="/admin/audit-logs", tags=["admin-audit"])


def _serialize(log: AuditLog) -> dict:
    return {
        "id": log.id,
        "trace_id": log.trace_id,
        "user_id": log.user_id,
        "user_email": log.user_email,
        "resource_type": log.resource_type,
        "resource_id": log.resource_id,
        "action": log.action,
        "method": log.method,
        "path": log.path,
        "ip": log.ip,
        "user_agent": log.user_agent,
        "status": log.status,
        "error_message": log.error_message,
        "extra": log.extra,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }


@router.get("/_options", summary="筛选下拉选项(resource_type / action / status 枚举)")
async def list_options(
    current: CurrentUser = Depends(require_permission(Permissions.SYSTEM_AUDIT)),
):
    return success({
        "resource_types": sorted(t.value for t in AuditResourceType),
        "actions": sorted(a.value for a in AuditAction),
        "statuses": [AuditStatus.SUCCESS, AuditStatus.FAILED],
    })


@router.get("", summary="审计日志列表(多条件筛选 + 分页)")
async def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    resource_type: str | None = Query(None, max_length=50),
    action: str | None = Query(None, max_length=50),
    status: str | None = Query(None, max_length=20),
    user_email: str | None = Query(None, max_length=255, description="LIKE 模糊匹配"),
    trace_id: str | None = Query(None, max_length=36),
    start_at: datetime | None = Query(None, description="created_at >="),
    end_at: datetime | None = Query(None, description="created_at <="),
    current: CurrentUser = Depends(require_permission(Permissions.SYSTEM_AUDIT)),
    db: AsyncSession = Depends(get_db),
):
    items, total = await audit_query_service.list_audit_logs(
        db,
        page=page,
        page_size=page_size,
        resource_type=resource_type,
        action=action,
        status=status,
        user_email=user_email,
        trace_id=trace_id,
        start_at=start_at,
        end_at=end_at,
    )
    return success({
        "items": [_serialize(log) for log in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@router.get("/{log_id}", summary="审计日志单条详情(含完整 extra)")
async def get_log(
    log_id: int = Path(..., ge=1),
    current: CurrentUser = Depends(require_permission(Permissions.SYSTEM_AUDIT)),
    db: AsyncSession = Depends(get_db),
):
    log = await audit_query_service.get_audit_log(db, log_id=log_id)
    if log is None:
        raise NotFoundError("Audit log not found")
    return success(_serialize(log))
