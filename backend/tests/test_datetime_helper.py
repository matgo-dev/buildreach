"""to_naive_utc 单元测试。"""
from datetime import datetime, timezone, timedelta

import pytest

from app.core.datetime import to_naive_utc


def test_none_passthrough():
    assert to_naive_utc(None) is None


def test_naive_passthrough():
    dt = datetime(2026, 6, 10, 12, 0, 0)
    result = to_naive_utc(dt)
    assert result == dt
    assert result.tzinfo is None


def test_utc_aware_stripped():
    dt = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
    result = to_naive_utc(dt)
    assert result == datetime(2026, 6, 10, 12, 0, 0)
    assert result.tzinfo is None


def test_non_utc_converted():
    """东八区 20:00 → UTC 12:00,去 tzinfo。"""
    tz_cst = timezone(timedelta(hours=8))
    dt = datetime(2026, 6, 10, 20, 0, 0, tzinfo=tz_cst)
    result = to_naive_utc(dt)
    assert result == datetime(2026, 6, 10, 12, 0, 0)
    assert result.tzinfo is None
