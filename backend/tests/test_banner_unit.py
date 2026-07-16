"""Banner 纯逻辑单测 — 图片 URL 前缀拼接 + 横幅尺寸,不涉及 DB/HTTP。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from app.core.config import settings
from app.services.banner import _full_image_url
from app.services._buyer_utils import BANNER_TARGET_SIZE, _prepare_image_from_path


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


def _make_wide_png(width: int, height: int) -> str:
    from PIL import Image as PILImage
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    PILImage.new("RGB", (width, height), (30, 80, 60)).save(path, "PNG")
    return path


def test_banner_target_size_keeps_wide_resolution():
    """关键回归:横幅用 BANNER_TARGET_SIZE(1920),1600 宽不被缩糊到 800。"""
    path = _make_wide_png(1600, 640)
    try:
        _bytes, w, _h = _prepare_image_from_path(
            Path(path), "banner.png", target_size=BANNER_TARGET_SIZE,
        )
        assert w == 1600  # 1920 上界内,原样保留
    finally:
        os.unlink(path)


def test_default_target_size_still_shrinks_to_800():
    """默认(商品图)仍缩到 800,参数化未改动既有行为。"""
    path = _make_wide_png(1600, 640)
    try:
        _bytes, w, _h = _prepare_image_from_path(Path(path), "product.png")
        assert w == 800
    finally:
        os.unlink(path)
