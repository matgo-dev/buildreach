"""邮箱归一化 — 唯一真相源。

邮箱作为身份不区分大小写(对齐 Devise 默认 case_insensitive_keys/strip_whitespace_keys):
所有写入与查询入口先归一化再落库/比较,库里只存小写;
DB 侧 ck_users_email_normalized 兜底,漏归一化的写入直接失败而不是悄悄存入大小写变体。
"""
from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, EmailStr


def normalize_email(raw: str) -> str:
    return raw.strip().lower()


# 请求体里的登录邮箱字段统一用它:先按 EmailStr 校验格式,再归一化
NormalizedEmailStr = Annotated[EmailStr, AfterValidator(normalize_email)]
