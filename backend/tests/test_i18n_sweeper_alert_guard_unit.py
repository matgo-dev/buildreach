"""sweep 末尾的告警记录必须被隔离:告警侧抛错不能让扫描失败(翻译结果已落库)。"""
from __future__ import annotations

import asyncio
import logging

from app.services import i18n_sweeper, system_alerts


def test_alert_recorder_exception_is_swallowed_and_logged(monkeypatch, caplog):
    async def boom(stats, last_error):
        raise RuntimeError("alert side broken")

    monkeypatch.setattr(system_alerts, "record_translation_sweep", boom)
    monkeypatch.setattr(i18n_sweeper, "consume_last_provider_error", lambda: None)
    with caplog.at_level(logging.ERROR, logger="app.i18n_sweeper"):
        asyncio.run(i18n_sweeper._notify_sweep_result({"scanned": 3, "translated": 0, "failed": 3}))
    assert any("记录告警状态异常" in r.getMessage() for r in caplog.records)


def test_alert_recorder_receives_stats_and_consumed_error(monkeypatch):
    seen: list[tuple] = []

    async def record(stats, last_error):
        seen.append((stats, last_error))

    monkeypatch.setattr(system_alerts, "record_translation_sweep", record)
    monkeypatch.setattr(i18n_sweeper, "consume_last_provider_error", lambda: "HTTP 403 forbidden")
    stats = {"scanned": 5, "translated": 0, "failed": 5}
    asyncio.run(i18n_sweeper._notify_sweep_result(stats))
    assert seen == [(stats, "HTTP 403 forbidden")]
