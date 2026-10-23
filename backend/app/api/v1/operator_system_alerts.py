"""运营端系统告警:外部依赖(翻译服务等)故障时给内部账号看的横幅数据。

只给内部角色(OPERATOR/ADMIN);匿名 401、买家/供应商 403。
状态来自进程内存(见 services/system_alerts.py),这里只补一个待译行数(走 i18n_pending_at 索引)。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.core.exceptions import success
from app.core.i18n_registry import all_registered
from app.db.session import get_db
from app.rbac.guards import require_any_role
from app.services import system_alerts

router = APIRouter(prefix="/operator/system-alerts", tags=["operator-system-alerts"])


async def _count_pending_rows(db: AsyncSession) -> int:
    total = 0
    for model_cls in all_registered():
        res = await db.execute(
            select(func.count()).select_from(model_cls).where(model_cls.i18n_pending_at.isnot(None))
        )
        total += int(res.scalar_one())
    return total


@router.get("", summary="当前系统告警(内部账号)")
async def list_system_alerts(
    db: AsyncSession = Depends(get_db),
    _current: CurrentUser = Depends(require_any_role("OPERATOR", "ADMIN")),
):
    state = system_alerts.translation_state()
    pending = await _count_pending_rows(db) if state.is_down else None
    return success({"items": system_alerts.build_alert_items(state, pending)})
