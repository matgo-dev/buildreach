"""静态文件 MIME 类型补注册。

缩略图全是 .webp,而 slim 镜像没有 /etc/mime.types、Python 3.12 及以前的内置表也没有 webp,
StaticFiles 会把它们当 text/plain 返回。显式注册,不依赖运行环境的 MIME 表。
"""
from __future__ import annotations

import mimetypes

EXTRA_MIME_TYPES: dict[str, str] = {
    ".webp": "image/webp",
}


def register_extra_mime_types() -> None:
    for ext, mime in EXTRA_MIME_TYPES.items():
        mimetypes.add_type(mime, ext)
