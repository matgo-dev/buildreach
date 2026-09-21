"""密码规则:6-20 位,字母/数字/符号(可打印 ASCII,不含空格)至少两类。"""
from __future__ import annotations

import pytest

from app.core.security import validate_password_strength


@pytest.mark.parametrize(
    "pwd",
    [
        "abc123",            # 字母+数字,下限 6 位
        "abc!@#",            # 字母+符号
        "123!@#",            # 数字+符号
        "Aa123456789!",      # 三类
        "a1" + "x" * 18,     # 上限 20 位
        "p@ss~{}[]|\\/`'\"",  # 各种标点都算符号
    ],
)
def test_accepts(pwd):
    assert validate_password_strength(pwd)


@pytest.mark.parametrize(
    "pwd",
    [
        "123456",            # 纯数字
        "abcdef",            # 纯字母
        "!@#$%^",            # 纯符号
        "ab12",              # 不足 6 位
        "a1" + "x" * 19,     # 超过 20 位
        "abc 123",           # 空格
        "abc123\t",          # 其它空白
        "密码abc123",         # 非 ASCII
    ],
)
def test_rejects(pwd):
    assert not validate_password_strength(pwd)
