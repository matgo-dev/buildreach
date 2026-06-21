"""统一 Storage 适配层 — 业务只认 file_key,不碰文件在本地还是 OSS。

本期实现 LocalDiskStorage;未来 OssStorage 仅新增实现 + 配置 + DI,业务不动。
"""
from __future__ import annotations

import logging
import os
import shutil
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Protocol, runtime_checkable

from app.core.config import settings

logger = logging.getLogger(__name__)


@runtime_checkable
class Storage(Protocol):
    """存储协议:业务层唯一入口,从不直接 import oss2 或 open(本地路径)。"""

    def save(self, file_key: str, stream: BinaryIO) -> None:
        """将流写入存储。"""
        ...

    def open(self, file_key: str) -> BinaryIO:
        """返回可读二进制流(不是本地路径)。"""
        ...

    def delete(self, file_key: str) -> None:
        """删除文件(best-effort)。"""
        ...

    def exists(self, file_key: str) -> bool:
        """文件是否存在。"""
        ...

    def public_url(self, key: str) -> str:
        """公开资产 URL(商品图,走 CDN);敏感件不用。"""
        ...


class LocalDiskStorage:
    """本地磁盘存储 — 附件私有目录,不经 /static 公开。"""

    def __init__(self, base_dir: str | Path) -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    def _path(self, file_key: str) -> Path:
        # 防路径穿越:只取文件名部分
        safe_name = Path(file_key).name
        return self._base / safe_name

    def save(self, file_key: str, stream: BinaryIO) -> None:
        target = self._path(file_key)
        tmp = target.with_suffix(target.suffix + ".tmp")
        try:
            with open(tmp, "wb") as f:
                shutil.copyfileobj(stream, f)
                f.flush()
                os.fsync(f.fileno())
            tmp.rename(target)
        except BaseException:
            # 写失败,清理临时文件
            tmp.unlink(missing_ok=True)
            raise

    def open(self, file_key: str) -> BinaryIO:
        target = self._path(file_key)
        if not target.is_file():
            raise FileNotFoundError(f"Storage file not found: {file_key}")
        return open(target, "rb")

    def delete(self, file_key: str) -> None:
        target = self._path(file_key)
        target.unlink(missing_ok=True)

    def exists(self, file_key: str) -> bool:
        return self._path(file_key).is_file()

    def public_url(self, key: str) -> str:
        return f"{settings.IMAGE_BASE_URL}/{key}"


# ── 单例(启动时初始化) ──

_PRIVATE_UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "private_uploads" / "attachments"

_attachment_storage: LocalDiskStorage | None = None


def get_attachment_storage() -> LocalDiskStorage:
    """获取附件存储单例(懒初始化)。"""
    global _attachment_storage
    if _attachment_storage is None:
        _attachment_storage = LocalDiskStorage(_PRIVATE_UPLOADS_DIR)
    return _attachment_storage
