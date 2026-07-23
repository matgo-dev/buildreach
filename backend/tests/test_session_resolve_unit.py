"""resolve_stale_refresh 纯函数单测:CAS 未命中后的重读判定。"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.services.session_service import GRACE_WINDOW_SECONDS, resolve_stale_refresh

NOW = datetime(2026, 7, 22, 12, 0, 0)  # naive UTC


def _resolve(*, presented, current="cur", prev="prv", rotated_delta=0, expires_delta=3600):
    return resolve_stale_refresh(
        current_jti=current,
        prev_jti=prev,
        rotated_at=NOW - timedelta(seconds=rotated_delta),
        expires_at=NOW + timedelta(seconds=expires_delta),
        presented_jti=presented,
        now=NOW,
    )


def test_expired_wins_even_if_prev_matches():
    """行已过期 → EXPIRED,优先级高于 grace。"""
    assert _resolve(presented="prv", rotated_delta=1, expires_delta=-1) == "EXPIRED"


def test_prev_within_grace_window():
    assert _resolve(presented="prv", rotated_delta=GRACE_WINDOW_SECONDS - 1) == "GRACE"


def test_prev_at_exact_window_boundary_is_kill():
    """窗口是严格小于:恰好 60s → KILL。"""
    assert _resolve(presented="prv", rotated_delta=GRACE_WINDOW_SECONDS) == "KILL"


def test_prev_none_is_kill():
    assert _resolve(presented="whatever", prev=None, rotated_delta=1) == "KILL"


def test_unknown_jti_is_kill():
    """既非 current 也非 prev(更老的代)→ 重放,KILL。"""
    assert _resolve(presented="ancient", rotated_delta=1) == "KILL"
