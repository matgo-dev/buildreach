"""内部组织搜索的纯逻辑:LIKE 通配符转义。"""
from __future__ import annotations

import pytest

from app.api.v1.internal import _escape_like


@pytest.mark.parametrize("raw, expected", [
    ("Acme", "Acme"),
    ("100%", "100\\%"),
    ("a_b", "a\\_b"),
    ("back\\slash", "back\\\\slash"),
    ("%_\\", "\\%\\_\\\\"),
    ("", ""),
])
def test_escape_like(raw, expected):
    assert _escape_like(raw) == expected


def test_escape_like_is_idempotent_on_plain_text():
    plain = "Kilimanjaro Builders Ltd"
    assert _escape_like(_escape_like(plain)) == plain
