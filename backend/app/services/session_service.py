"""前台会话账本 service:签发 / 轮换 / 吊销 / 清理。

设计:docs/specs/2026-07-22-前台refresh会话吊销-设计.md
时间一律 naive UTC(app.db.base._utcnow),与全项目 DB 约定一致。
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.db.base import _utcnow
from app.db.models.auth_session import AuthSession
from app.db.models.user import User

# 宽限窗:refresh cookie 全 tab 共享,多 tab 并发刷新是日常;
# 窗口内收到 prev_jti 视为并发重试而非重放(设计 §4)
GRACE_WINDOW_SECONDS = 60

# 单用户最大会话数:堵"凭据持有者刷登录"的无界增长路径
MAX_SESSIONS_PER_USER = 10
# 全局过期行批清:时间门控 + 单次上限(单进程内存态,与限流/调度同基调)
GLOBAL_SWEEP_INTERVAL_SECONDS = 3600
GLOBAL_SWEEP_BATCH_LIMIT = 1000
_last_global_sweep: float = 0.0


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
    # 注:presented==current 走不到这里(CAS 会直接命中 ROTATED;过期则上面已 EXPIRED),
    # 此兜底 KILL 只为防御性完整。current_jti 参数因此在本函数内未被比较,由调用方用于 GRACE 重发。
    return "KILL"


async def issue_session_tokens(db: AsyncSession, user: User) -> dict:
    """插会话行 → flush 拿 sid → commit 成功后才签 token。

    统一签发口:login / register_buyer / change_password / 旧格式兼容迁移全走这里,
    杜绝"token 指向不存在的会话"。
    """
    now = _utcnow()
    jti = str(uuid4())
    row = AuthSession(
        user_id=user.id,
        current_jti=jti,
        prev_jti=None,
        rotated_at=now,
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(row)
    await db.flush()
    sid = row.id
    await db.commit()

    access_token, expires_in = create_access_token(user.id, user.email, user.token_version)
    refresh_token = create_refresh_token(
        user.id, user.email, user.token_version, sid=sid, jti=jti
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": expires_in,
    }


async def rotate_or_resolve(
    db: AsyncSession, *, sid: int, user_id: int, presented_jti: str
) -> tuple[str, str | None]:
    """refresh 轮换:原子 CAS,未命中则重读判定。

    返回 (status, jti):
    - ("ROTATED", 新jti)   正常轮换,签新对 token
    - ("GRACE", current)   多 tab 并发重试,幂等重发 current,不改行
    - ("KILLED", None)     重放,行已删,调用方写审计 + 401
    - ("EXPIRED", None)    行过期,已删,401
    - ("MISSING", None)    无行(已吊销/已清理),401
    """
    now = _utcnow()
    new_jti = str(uuid4())
    result = await db.execute(
        update(AuthSession)
        .where(
            AuthSession.id == sid,
            AuthSession.user_id == user_id,
            AuthSession.current_jti == presented_jti,
            AuthSession.expires_at > now,
        )
        .values(
            prev_jti=AuthSession.current_jti,  # SQL 端取旧值,单条 UPDATE 内原子
            current_jti=new_jti,
            rotated_at=now,
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    if result.rowcount == 1:
        await db.commit()
        return ("ROTATED", new_jti)

    row = (
        await db.execute(
            select(AuthSession).where(
                AuthSession.id == sid, AuthSession.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return ("MISSING", None)

    decision = resolve_stale_refresh(
        current_jti=row.current_jti,
        prev_jti=row.prev_jti,
        rotated_at=row.rotated_at,
        expires_at=row.expires_at,
        presented_jti=presented_jti,
        now=now,
    )
    if decision == "GRACE":
        return ("GRACE", row.current_jti)
    # KILL / EXPIRED → 删行
    await db.execute(delete(AuthSession).where(AuthSession.id == sid))
    await db.commit()
    return ("KILLED" if decision == "KILL" else "EXPIRED", None)


async def revoke_session(db: AsyncSession, *, sid: int, user_id: int) -> None:
    """吊销单会话(logout 本设备)。不 commit,调用方负责。"""
    await db.execute(
        delete(AuthSession).where(AuthSession.id == sid, AuthSession.user_id == user_id)
    )


async def revoke_all_sessions(db: AsyncSession, *, user_id: int) -> None:
    """吊销该用户全部会话(tv bump 触点配套)。不 commit,调用方负责。"""
    await db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))


async def cleanup_on_login(db: AsyncSession, *, user_id: int) -> None:
    """登录路径清理(不 commit,与登录同事务落库):

    1. 删本用户过期行
    2. 非过期会话数 ≥ MAX 时删最旧,保留 MAX-1 条(为即将签发的新会话腾位)
    3. 时间门控的全局过期批清(兜底"一次登录后流失"的用户永久留行)
    """
    global _last_global_sweep
    now = _utcnow()

    await db.execute(
        delete(AuthSession).where(
            AuthSession.user_id == user_id, AuthSession.expires_at <= now
        )
    )

    ids = (
        await db.execute(
            select(AuthSession.id)
            .where(AuthSession.user_id == user_id)
            .order_by(AuthSession.rotated_at.desc())
        )
    ).scalars().all()
    if len(ids) >= MAX_SESSIONS_PER_USER:
        await db.execute(
            delete(AuthSession).where(
                AuthSession.id.in_(ids[MAX_SESSIONS_PER_USER - 1:])
            )
        )

    if time.monotonic() - _last_global_sweep >= GLOBAL_SWEEP_INTERVAL_SECONDS or _last_global_sweep == 0.0:
        _last_global_sweep = time.monotonic()
        await db.execute(
            delete(AuthSession).where(
                AuthSession.id.in_(
                    select(AuthSession.id)
                    .where(AuthSession.expires_at <= now)
                    .limit(GLOBAL_SWEEP_BATCH_LIMIT)
                )
            )
        )
