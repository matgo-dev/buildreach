"""邮箱归一化:去首尾空白 + 整体转小写(身份比较不区分大小写,对齐 Devise 默认)。"""
from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from app.core.email import NormalizedEmailStr, normalize_email


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("john@gmail.com", "john@gmail.com"),
        ("John.Doe@Gmail.COM", "john.doe@gmail.com"),
        ("  John@Gmail.com\t", "john@gmail.com"),
    ],
)
def test_normalize_email(raw, expected):
    assert normalize_email(raw) == expected


class _M(BaseModel):
    email: NormalizedEmailStr


def test_normalized_email_str_lowercases_after_validation():
    assert _M(email=" John@Gmail.COM ").email == "john@gmail.com"


def test_normalized_email_str_still_validates_format():
    with pytest.raises(ValidationError):
        _M(email="not-an-email")
