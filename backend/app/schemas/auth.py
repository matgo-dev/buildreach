"""认证相关 schemas。"""
from __future__ import annotations

import re

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.constants.country_registration import (
    COUNTRY_CODES,
    COUNTRY_META,
    LANGUAGE_CODES,
    REGISTRATION_NO_MAX_LENGTH,
    validate_registration_no,
)
from app.core.security import PASSWORD_RULE_MESSAGE, validate_password_strength


# 用户名规则:3-50 位,字母/数字/下划线/短横,不能纯数字
USERNAME_REGEX = re.compile(r"^(?![0-9]+$)[A-Za-z0-9_\-]{3,50}$")

# 统一社会信用代码:严格 18 位,大写字母 + 数字(国标 GB 32100-2015)
USC_REGEX = re.compile(r"^[0-9A-Z]{18}$")

# 中国大陆手机号:11 位,1 开头,第二位 3-9(BUYER 仍走严格规则)
PHONE_REGEX = re.compile(r"^1[3-9]\d{9}$")

# SUPPLIER 占位手机号规则:覆盖各国格式的弱校验,TODO(I18N-PHONE) 各国精确规则待补
SUPPLIER_PHONE_REGEX = re.compile(r"^[+0-9\s\-]{6,20}$")


def _validate_password(v: str) -> str:
    if not validate_password_strength(v):
        raise ValueError(PASSWORD_RULE_MESSAGE)
    return v


def _validate_username_optional(v: str | None) -> str | None:
    if v is None or v == "":
        return None
    if not USERNAME_REGEX.match(v):
        raise ValueError("用户名 3-50 位,只能含字母/数字/下划线/短横,且不能纯数字")
    return v


def _validate_phone_optional(v: str | None) -> str | None:
    """phone 选填;若提供必须是中国大陆 11 位手机号。"""
    if v is None or v == "":
        return None
    if not PHONE_REGEX.match(v):
        raise ValueError("手机号必须是 11 位中国大陆号码(1 开头,第二位 3-9)")
    return v


class BuyerRegisterIn(BaseModel):
    email: EmailStr
    username: str | None = Field(default=None, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    password: str
    # 公司信息:按统一社会信用代码识别企业(不存在则建新组织,存在则加入)
    company_name: str = Field(..., min_length=1, max_length=200)
    unified_social_credit_code: str = Field(..., min_length=18, max_length=18)

    @field_validator("password")
    @classmethod
    def _check_pwd(cls, v: str) -> str:
        return _validate_password(v)

    @field_validator("username")
    @classmethod
    def _check_username(cls, v: str | None) -> str | None:
        return _validate_username_optional(v)

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, v: str | None) -> str | None:
        return _validate_phone_optional(v)

    @field_validator("unified_social_credit_code")
    @classmethod
    def _check_usc(cls, v: str) -> str:
        if not USC_REGEX.match(v):
            raise ValueError("统一社会信用代码必须为 18 位大写字母与数字")
        return v


class SupplierRegisterIn(BaseModel):
    """供应商自助注册入参(PRD v1.3 §2.2)。

    相对 BUYER:去掉 username,加 country_code / language_preference / registration_no。
    phone 已由路由层归一化为 E.164,schema 只做基本长度校验。
    """

    # `extra='forbid'` 让多带 `username` 等未声明字段直接 422,确认入参契约
    model_config = {"extra": "forbid"}

    email: EmailStr
    name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=6, max_length=20)
    phone_region: str | None = Field(default=None, max_length=2)
    password: str
    company_name: str = Field(..., min_length=1, max_length=200)
    country_code: str = Field(..., min_length=2, max_length=2)
    registration_no: str = Field(..., min_length=1, max_length=REGISTRATION_NO_MAX_LENGTH)
    language_preference: str = Field(..., min_length=2, max_length=35)

    @field_validator("password")
    @classmethod
    def _check_pwd(cls, v: str) -> str:
        return _validate_password(v)

    @field_validator("country_code")
    @classmethod
    def _check_country(cls, v: str) -> str:
        if v not in COUNTRY_CODES:
            raise ValueError(f"country_code 必须是 9 国之一:{','.join(COUNTRY_CODES)}")
        return v

    @model_validator(mode="after")
    def _check_registration_no_format(self) -> "SupplierRegisterIn":
        # 后端兜底:按国别精确校验注册号格式(前端可绕过,后端必须兜底,与前端正则对齐)
        if not validate_registration_no(self.country_code, self.registration_no):
            hint = COUNTRY_META.get(self.country_code, {}).get("reg_no_hint", "格式不符")
            raise ValueError(f"注册号格式不符,应为:{hint}")
        return self

    @field_validator("language_preference")
    @classmethod
    def _check_lang(cls, v: str) -> str:
        if v not in LANGUAGE_CODES:
            raise ValueError(f"language_preference 必须是合法语言 code 之一:{','.join(LANGUAGE_CODES)}")
        return v


class RegisterOut(BaseModel):
    user_id: int
    email: str | None = None


class LoginIn(BaseModel):
    # identifier:邮箱(含 @) / 手机号(纯数字或 + 前缀) / 用户名
    identifier: str = Field(..., min_length=3, max_length=255)
    password: str
    # 手机号登录时的国家码(TZ / CN),与注册对称
    phone_region: str | None = Field(default=None, max_length=2)


class TokenOut(BaseModel):
    """登录响应。refresh_token **不在 body**,通过 httpOnly cookie 下发。"""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _check_new(cls, v: str) -> str:
        if not validate_password_strength(v):
            raise ValueError(PASSWORD_RULE_MESSAGE)
        return v


class OrganizationOut(BaseModel):
    type: str
    id: int
    name: str
    is_owner: bool
    # 前端 dashboard banner 判定用:SupplierOrg.status / BuyerOrg.status
    status: str | None = None
    # 买方组织统一社会信用代码(供 owner 自助维护 + 运营授权检索);supplier 恒 None
    unified_social_credit_code: str | None = None


class ZoneOut(BaseModel):
    code: str
    name_zh: str
    name_en: str | None = None


class MeOut(BaseModel):
    id: int
    email: str | None = None
    username: str | None = None
    name: str
    phone: str | None = None
    status: str
    must_change_password: bool
    language_preference: str | None = None
    roles: list[str]
    permissions: list[str]
    organization: OrganizationOut | None = None
    is_demo: bool = False
    zones: list[ZoneOut] = []
