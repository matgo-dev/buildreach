"""轮播 Banner Pydantic schemas。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BannerOut(BaseModel):
    """公开 API 返回(按 locale 填充 title)。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None = None  # locale 化
    image_url: str
    link_url: str | None = None
    sort_order: int = 0
    position: str = "home_carousel"


class BannerDetailOut(BaseModel):
    """Operator 管理 API 返回(含全部字段)。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title_zh: str | None = None
    title_en: str | None = None
    title_sw: str | None = None
    image_url: str  # 相对 key(banners/xxx.jpg),可回传给创建/更新
    image_full_url: str | None = None  # 拼好前缀的完整路径,仅供预览
    link_url: str | None = None
    sort_order: int = 0
    is_active: bool = True
    position: str = "home_carousel"
    start_at: datetime | None = None
    end_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BannerCreate(BaseModel):
    title_zh: str | None = None
    title_en: str | None = None
    title_sw: str | None = None
    image_url: str = Field(..., max_length=500)
    link_url: str | None = Field(None, max_length=500)
    sort_order: int = 0
    is_active: bool = True
    position: str = Field("home_carousel", max_length=50)
    start_at: datetime | None = None
    end_at: datetime | None = None


class BannerUpdate(BaseModel):
    title_zh: str | None = None
    title_en: str | None = None
    title_sw: str | None = None
    image_url: str | None = Field(None, max_length=500)
    link_url: str | None = Field(None, max_length=500)
    sort_order: int | None = None
    is_active: bool | None = None
    position: str | None = Field(None, max_length=50)
    start_at: datetime | None = None
    end_at: datetime | None = None
