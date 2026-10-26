"""系统告警 — 外部依赖(翻译服务等)悄悄挂掉时的通知路径。

状态只在进程内存(单进程部署,见 docs 单进程约束),重启后下一轮扫描(≤5 分钟)即刷新。
判定/限流是纯函数,sweep 侧只负责喂结果;接口侧只读快照。

以后 Resend 发信失败、OSS 上传失败等也往 `get_alerts()` 挂,运营端横幅不用再改。
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("app.system_alerts")

ALERT_EMAIL_MIN_INTERVAL = timedelta(days=1)

KIND_TRANSLATION_DOWN = "translation_down"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# 纯逻辑
# ---------------------------------------------------------------------------

def is_provider_down(stats: dict[str, int]) -> bool:
    """一轮扫描 `translated=0 且 failed>0` ⇒ 翻译提供方故障,而不是个别行的问题。"""
    return stats.get("translated", 0) == 0 and stats.get("failed", 0) > 0


@dataclass
class TranslationHealth:
    down_since: datetime | None = None
    last_error: str | None = None
    last_failed_rows: int = 0
    last_run_at: datetime | None = None
    last_alert_sent_at: datetime | None = None

    @property
    def is_down(self) -> bool:
        return self.down_since is not None


def apply_sweep_result(
    state: TranslationHealth,
    stats: dict[str, int],
    last_error: str | None,
    now: datetime,
) -> str:
    """把一轮扫描结果记进状态,返回状态迁移:

    - "down_started": 刚判定故障(应发告警邮件)
    - "still_down":   持续故障(按日限流决定是否再发)
    - "recovered":    故障解除(应发恢复邮件)
    - "ok":           一直正常

    没扫到行(scanned=0)视为正常:没有待译任务就不存在"正在失败"。
    """
    state.last_run_at = now
    state.last_failed_rows = stats.get("failed", 0)
    if last_error:
        state.last_error = last_error

    down = is_provider_down(stats)
    if down and state.down_since is None:
        state.down_since = now
        return "down_started"
    if down:
        return "still_down"
    if state.down_since is not None:
        state.down_since = None
        state.last_alert_sent_at = None
        state.last_error = None
        return "recovered"
    return "ok"


def should_send_alert(state: TranslationHealth, transition: str, now: datetime) -> bool:
    """同一故障每天最多一封;恢复时再发一封。"""
    if transition == "recovered":
        return True
    if transition not in ("down_started", "still_down"):
        return False
    if state.last_alert_sent_at is None:
        return True
    return now - state.last_alert_sent_at >= ALERT_EMAIL_MIN_INTERVAL


def build_alert_items(state: TranslationHealth, pending_rows: int | None) -> list[dict]:
    """给运营端横幅的快照。文案由前端按 locale 拼,这里只给结构化字段。"""
    if not state.is_down:
        return []
    return [{
        "kind": KIND_TRANSLATION_DOWN,
        "since": state.down_since.isoformat() if state.down_since else None,
        "detail": state.last_error,
        "pending_rows": pending_rows if pending_rows is not None else state.last_failed_rows,
    }]


# ---------------------------------------------------------------------------
# 进程内状态 + 接线
# ---------------------------------------------------------------------------

_translation = TranslationHealth()


def translation_state() -> TranslationHealth:
    return _translation


def reset_for_tests() -> None:
    global _translation
    _translation = TranslationHealth()


async def record_translation_sweep(stats: dict[str, int], last_error: str | None) -> None:
    """sweep 每轮结束后调用:更新状态,必要时发邮件。邮件失败只记日志,不影响扫描。"""
    from app.core.config import settings
    from app.services.email_service import send_system_alert_email

    now = _now()
    transition = apply_sweep_result(_translation, stats, last_error, now)
    if transition == "down_started":
        logger.error(
            "翻译服务判定故障: translated=0 failed=%d 最后错误=%s",
            stats.get("failed", 0), last_error,
        )
    elif transition == "recovered":
        logger.info("翻译服务已恢复")

    if not should_send_alert(_translation, transition, now):
        return
    if not settings.alert_emails:
        return

    if transition == "recovered":
        subject = "[Matgo] 翻译服务已恢复"
        body = f"翻译扫描器已重新翻译成功(translated={stats.get('translated', 0)})。\n时间: {now.isoformat()}"
    else:
        since = _translation.down_since.isoformat() if _translation.down_since else "?"
        subject = "[Matgo] 翻译服务异常"
        body = (
            f"翻译扫描器连续失败,判定翻译提供方故障。\n"
            f"故障开始: {since}\n"
            f"本轮失败行数: {stats.get('failed', 0)}\n"
            f"最后错误: {last_error or _translation.last_error or '(无错误原文)'}\n\n"
            f"同一故障每天最多发一封;恢复后会再发一封。"
        )
    # 不管发没发成功都记时间:发信失败已在 email_service 记了日志,不要每 5 分钟重试刷 SMTP
    if transition != "recovered":
        _translation.last_alert_sent_at = now
    await asyncio.to_thread(send_system_alert_email, subject, body)
