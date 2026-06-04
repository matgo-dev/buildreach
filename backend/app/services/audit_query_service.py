"""审计日志查询 service。

只读;GET 类查询本身**不写**审计(避免日志爆炸,与方案 §6.3 一致)。
"""
from __future__ import annotations

from datetime import datetime
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog


async def list_audit_logs(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 50,
    resource_type: str | None = None,
    action: str | None = None,
    status: str | None = None,
    user_email: str | None = None,
    trace_id: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> tuple[Sequence[AuditLog], int]:
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    offset = (page - 1) * page_size

    conditions = []
    if resource_type:
        conditions.append(AuditLog.resource_type == resource_type)
    if action:
        conditions.append(AuditLog.action == action)
    if status:
        conditions.append(AuditLog.status == status)
    if user_email:
        # 模糊匹配
        conditions.append(AuditLog.user_email.ilike(f"%{user_email}%"))
    if trace_id:
        conditions.append(AuditLog.trace_id == trace_id)
    if start_at:
        conditions.append(AuditLog.created_at >= start_at)
    if end_at:
        conditions.append(AuditLog.created_at <= end_at)

    base = select(AuditLog).where(*conditions)
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    rows = await db.execute(
        base.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    return rows.scalars().all(), int(total)


async def get_audit_log(db: AsyncSession, *, log_id: int) -> AuditLog | None:
    return await db.get(AuditLog, log_id)
