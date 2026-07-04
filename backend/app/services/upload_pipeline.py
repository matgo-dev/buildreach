"""Upload pipeline helpers: bounded streaming, temp files, and thread offload."""
from __future__ import annotations

import asyncio
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable, TypeVar

from fastapi import UploadFile

from app.core.config import settings

UPLOAD_CHUNK_SIZE = 1024 * 1024
SNIFF_BYTES = 8192
# 中转临时目录走系统 /tmp(恒可写、进程退出自动清、尊重 TMPDIR),
# 不放源码树下的 /app/tmp —— 后者在非 root 容器里不可写会导致上传 500。
_TMP_UPLOAD_DIR = Path(tempfile.gettempdir()) / "buildreach_uploads"
_T = TypeVar("_T")

_image_processing_semaphore = asyncio.Semaphore(
    max(1, settings.IMAGE_PROCESSING_CONCURRENCY)
)


@dataclass(slots=True)
class TempUpload:
    path: Path
    size: int
    head: bytes

    def cleanup(self) -> None:
        self.path.unlink(missing_ok=True)


def _create_temp_path(suffix: str) -> tuple[int, Path]:
    _TMP_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="upload_", suffix=suffix, dir=_TMP_UPLOAD_DIR)
    return fd, Path(name)


def _append_head(head: bytearray, chunk: bytes) -> None:
    if len(head) >= SNIFF_BYTES:
        return
    need = SNIFF_BYTES - len(head)
    head.extend(chunk[:need])


async def stream_upload_file_to_temp(
    file: UploadFile,
    *,
    max_size: int,
    suffix: str = "",
) -> TempUpload:
    """Stream a FastAPI UploadFile to a bounded temp file."""
    fd, path = _create_temp_path(suffix)
    head = bytearray()
    total = 0
    try:
        with os.fdopen(fd, "wb") as out:
            while True:
                chunk = await file.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_size:
                    raise ValueError("upload too large")
                _append_head(head, chunk)
                await asyncio.to_thread(out.write, chunk)
            await asyncio.to_thread(out.flush)
            await asyncio.to_thread(os.fsync, out.fileno())
        return TempUpload(path=path, size=total, head=bytes(head))
    except BaseException:
        path.unlink(missing_ok=True)
        raise


async def stream_binary_to_temp(
    stream: BinaryIO,
    *,
    max_size: int,
    suffix: str = "",
) -> TempUpload:
    """Stream a sync BinaryIO to a bounded temp file without collecting chunks."""
    fd, path = _create_temp_path(suffix)
    head = bytearray()
    total = 0
    try:
        with os.fdopen(fd, "wb") as out:
            while True:
                chunk = await asyncio.to_thread(stream.read, UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_size:
                    raise ValueError("upload too large")
                _append_head(head, chunk)
                await asyncio.to_thread(out.write, chunk)
            await asyncio.to_thread(out.flush)
            await asyncio.to_thread(os.fsync, out.fileno())
        return TempUpload(path=path, size=total, head=bytes(head))
    except BaseException:
        path.unlink(missing_ok=True)
        raise


async def run_image_processing(func: Callable[..., _T], *args, **kwargs) -> _T:
    """Run CPU-heavy Pillow work off the event loop with process-local backpressure."""
    async with _image_processing_semaphore:
        return await asyncio.to_thread(func, *args, **kwargs)
