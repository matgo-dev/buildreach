from __future__ import annotations

import io
import tempfile

import pytest
from PIL import Image

from app.core.config import settings
from app.core.exceptions import BusinessError
from app.services import upload_pipeline
from app.services._buyer_utils import save_uploaded_image_from_path


def test_temp_upload_dir_lives_under_system_tmp():
    """中转临时目录必须在系统 /tmp 下,不能是源码树相对路径。

    根因守卫:曾用 /app/tmp,非 root 容器里 /app 不可写 → 上传图片 500。
    """
    assert str(upload_pipeline._TMP_UPLOAD_DIR).startswith(tempfile.gettempdir())


@pytest.mark.asyncio
async def test_stream_binary_to_temp_writes_file_and_captures_head(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(upload_pipeline, "_TMP_UPLOAD_DIR", tmp_path)

    payload = b"abcdef" * 2048
    temp_upload = await upload_pipeline.stream_binary_to_temp(
        io.BytesIO(payload),
        max_size=len(payload),
        suffix=".bin",
    )
    try:
        assert temp_upload.size == len(payload)
        assert temp_upload.head == payload[: upload_pipeline.SNIFF_BYTES]
        assert temp_upload.path.read_bytes() == payload
    finally:
        temp_upload.cleanup()

    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_stream_binary_to_temp_rejects_oversize_and_cleans_tmp(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(upload_pipeline, "_TMP_UPLOAD_DIR", tmp_path)

    stream = io.BytesIO(b"x" * 16)
    with pytest.raises(ValueError):
        await upload_pipeline.stream_binary_to_temp(stream, max_size=8, suffix=".bin")

    assert list(tmp_path.iterdir()) == []


def test_image_processing_rejects_excessive_pixels(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "IMAGE_MAX_PIXELS", 100)
    source = tmp_path / "large-pixels.png"
    Image.new("RGB", (20, 20), (120, 120, 120)).save(source, format="PNG")

    with pytest.raises(BusinessError) as exc:
        save_uploaded_image_from_path(source, "large-pixels.png", "products/test")

    assert exc.value.biz_code == 42207
