"""自助资料管理 schemas(POST/PATCH /auth/me/*)。"""
from __future__ import annotations

import re

from pydantic import BaseModel, EmailStr, Field, field_validator

# 与 schemas/auth.py 中的 USERNAME_REGEX 保持一致
USERNAME_REGEX = re.compile(r"^(?![0-9]+$)[A-Za-z0-9_\-]{3,50}$")


class ProfileUpdateIn(BaseModel):
    """改基础资料:name / phone(低风险,无需密码)。

    PATCH 语义:不传的字段 = 不修改;空字符串视作清空(仅对可空字段 phone 有效)。
    """

    name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)


class ChangeEmailIn(BaseModel):
    """改登录邮箱(敏感:需要 current_password)。"""

    new_email: EmailStr
    current_password: str = Field(..., min_length=1)


class ChangeUsernameIn(BaseModel):
    """改/清空登录用户名(敏感:需要 current_password)。

    new_username 为空字符串或 null 表示清空(此后只能用邮箱登录)。
    """

    new_username: str | None = Field(default=None, max_length=50)
    current_password: str = Field(..., min_length=1)

    @field_validator("new_username")
    @classmethod
    def _check(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if not USERNAME_REGEX.match(v):
            raise ValueError("用户名 3-50 位,只能含字母/数字/下划线/短横,且不能纯数字")
        return v


# 中国大陆手机号:11 位,1 开头,第二位 3-9(与 schemas/auth.py 保持一致)
PHONE_REGEX = re.compile(r"^1[3-9]\d{9}$")


class ChangePhoneIn(BaseModel):
    """改/清空登录手机号(敏感:需要 current_password)。

    new_phone 为空字符串或 null 表示清空(此后不能用手机号登录)。
    """

    new_phone: str | None = Field(default=None, max_length=30)
    current_password: str = Field(..., min_length=1)

    @field_validator("new_phone")
    @classmethod
    def _check(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if not PHONE_REGEX.match(v):
            raise ValueError("手机号必须是 11 位中国大陆号码(1 开头,第二位 3-9)")
        return v
