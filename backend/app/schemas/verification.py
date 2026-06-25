"""验证码相关 Request/Response Schema。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class SendCodeIn(BaseModel):
    email: EmailStr
    purpose: Literal["REGISTER", "RESET_PASSWORD"]


class SendCodeOut(BaseModel):
    message: str
    expires_in: int


class VerifyCodeIn(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    purpose: Literal["REGISTER", "RESET_PASSWORD"]


class VerifyCodeOut(BaseModel):
    verification_token: str
    expires_in: int


class ResetPasswordIn(BaseModel):
    verification_token: str
    new_password: str = Field(..., min_length=11, max_length=50)
    confirm_password: str = Field(..., min_length=11, max_length=50)
