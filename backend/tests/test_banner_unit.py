"""Banner 纯逻辑单测 — 图片 URL 前缀拼接,不涉及 DB/HTTP。"""
from __future__ import annotations

from app.core.config import settings
from app.services.banner import _full_image_url


def test_full_image_url_prefixes_relative_key():
    """相对 key 拼上 IMAGE_PATH_PREFIX。"""
    prefix = settings.IMAGE_PATH_PREFIX.rstrip("/")
    assert _full_image_url("banners/x.jpg") == f"{prefix}/banners/x.jpg"


def test_full_image_url_strips_leading_slash():
    """带前导斜杠的 key 不产生双斜杠。"""
    prefix = settings.IMAGE_PATH_PREFIX.rstrip("/")
    assert _full_image_url("/banners/x.jpg") == f"{prefix}/banners/x.jpg"


def test_full_image_url_no_double_static():
    """关键回归:相对 key 不含 static,拼接后只出现一次前缀(防 /static/static 404)。"""
    result = _full_image_url("banners/hero-main.jpg")
    assert result.count("/static") <= 1
    assert not result.startswith("/static/static")
