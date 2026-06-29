from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class VerificationPurpose:
    REGISTER = "REGISTER"
    RESET_PASSWORD = "RESET_PASSWORD"


class VerificationCode(Base, TimestampMixin):
    __tablename__ = "verification_codes"
    __table_args__ = (
        Index("ix_vc_email_purpose", "email", "purpose"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    @staticmethod
    def hash_code(code: str) -> str:
        return hashlib.sha256(code.encode()).hexdigest()
