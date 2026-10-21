import os
from pathlib import Path

from app.services.floor_image import (
    _FINGERPRINT_CACHE,
    file_fingerprint,
    floor_bg_image_url,
    floor_image_name,
)


def _write_floor(uploads: Path, name: str, content: bytes) -> Path:
    p = uploads / "floors" / f"{name}.webp"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


def test_floor_image_name_strips_prefix():
    assert floor_image_name("floor-safety") == "safety"
    assert floor_image_name("safety") == "safety"


def test_missing_file_has_no_version(tmp_path: Path):
    _FINGERPRINT_CACHE.clear()
    assert floor_bg_image_url("floor-safety", tmp_path) == "/static/floors/safety.webp"


def test_fingerprint_is_content_based_and_stable(tmp_path: Path):
    _FINGERPRINT_CACHE.clear()
    p = _write_floor(tmp_path, "safety", b"image-v1")
    url1 = floor_bg_image_url("floor-safety", tmp_path)
    assert url1.startswith("/static/floors/safety.webp?v=")
    fp1 = url1.rsplit("=", 1)[1]
    assert len(fp1) == 8 and int(fp1, 16) >= 0

    # 同一内容再复制一次(mtime 变、内容不变):指纹不变,不能无谓打穿缓存
    os.utime(p, ns=(p.stat().st_atime_ns + 10**9, p.stat().st_mtime_ns + 10**9))
    assert floor_bg_image_url("floor-safety", tmp_path) == url1

    # 内容变:指纹必须变,这是整个方案存在的意义
    _write_floor(tmp_path, "safety", b"image-v2")
    os.utime(p, ns=(p.stat().st_atime_ns + 10**9, p.stat().st_mtime_ns + 10**9))
    url2 = floor_bg_image_url("floor-safety", tmp_path)
    assert url2 != url1


def test_fingerprint_cache_hits_without_rereading(tmp_path: Path, monkeypatch):
    _FINGERPRINT_CACHE.clear()
    p = _write_floor(tmp_path, "tools", b"abc")
    fp = file_fingerprint(p)
    assert fp is not None

    # 第二次调用若 (mtime, size) 未变,不应再打开文件
    def _boom(*_a, **_k):
        raise AssertionError("fingerprint cache miss: file re-read")

    monkeypatch.setattr(Path, "open", _boom)
    assert file_fingerprint(p) == fp
