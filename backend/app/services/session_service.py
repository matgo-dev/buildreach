"""前台会话账本 service:签发 / 轮换 / 吊销 / 清理。

设计:docs/specs/2026-07-22-前台refresh会话吊销-设计.md
时间一律 naive UTC(app.db.base._utcnow),与全项目 DB 约定一致。
"""
from __future__ import annotations

from datetime import datetime

# 宽限窗:refresh cookie 全 tab 共享,多 tab 并发刷新是日常;
# 窗口内收到 prev_jti 视为并发重试而非重放(设计 §4)
GRACE_WINDOW_SECONDS = 60


def resolve_stale_refresh(
    *,
    current_jti: str,
    prev_jti: str | None,
    rotated_at: datetime,
    expires_at: datetime,
    presented_jti: str,
    now: datetime,
) -> str:
    """CAS 轮换未命中后,对重读行做判定(纯函数,无 I/O)。

    返回:
    - "EXPIRED": 行已过期(优先级最高)
    - "GRACE":  presented == prev 且距上次轮换 < 宽限窗 → 幂等重发 current
    - "KILL":   其余(更老的代 / 宽限外的 prev)→ 重放,杀会话
    """
    if expires_at <= now:
        return "EXPIRED"
    if (
        prev_jti is not None
        and presented_jti == prev_jti
        and (now - rotated_at).total_seconds() < GRACE_WINDOW_SECONDS
    ):
        return "GRACE"
    return "KILL"
