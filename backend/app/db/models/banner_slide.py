"""首页轮播 Banner — 支持多广告位、定时上下线。

图片通过 attachment 上传接口获取 URL,Operator 通过 CRUD API 管理。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampUpdateMixin
from app.db.i18n_mixin import I18nMixin


class BannerSlide(Base, TimestampUpdateMixin, I18nMixin):
    __tablename__ = "banner_slides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title_zh: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title_en: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title_sw: Mapped[str | None] = mapped_column(String(100), nullable=True)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    link_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # 广告位标识,为后续多位置预留
    position: Mapped[str] = mapped_column(
        String(50), nullable=False, default="home_carousel", server_default="home_carousel",
    )
    # 定时上下线(MVP 预留,暂不做过滤逻辑)
    start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
