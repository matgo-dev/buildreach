from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampUpdateMixin


class UserStatus:
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class User(Base, TimestampUpdateMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    # 用户名:选填,UNIQUE,登录时可作为 email 的替代凭证
    username: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # 手机号:UNIQUE,买方主登录凭证(坦桑 +255 E.164),其他角色选填
    phone: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=UserStatus.ACTIVE)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 会话吊销版本号:嵌入 JWT tv claim,改密/强制下线时 +1,使旧 token 一次失效
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # 用户语言偏好(本轮仅 SUPPLIER 自助注册 Step 2 写入,其他场景为 NULL;TODO(T-LANG-CHANGE) 用户自助切换入口)
    language_preference: Mapped[str | None] = mapped_column(String(35), nullable=True)
