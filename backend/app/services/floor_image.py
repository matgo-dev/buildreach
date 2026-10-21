"""首页楼层背景图 URL:带内容指纹,换图即换 URL,缓存自然失效。

楼层图存 uploads/floors/<name>.webp,经 /static 公开。生产前面有 Cloudflare,会把 /static
缓存数小时并改写浏览器缓存,源站 no-cache 管不住;唯一可靠的做法是 URL 随内容变
(与 Next 的 /_next/static 文件名带哈希同理)。换图 = 把新文件复制进卷,不发版、不改配置。

指纹 = 文件内容 sha256 前 8 位。按 (mtime_ns, size) 缓存哈希结果,文件不变就不重读;
重新复制同一份内容(mtime 变、内容不变)指纹不变,不会无谓打穿缓存。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from app.core.config import settings
from app.services._buyer_utils import UPLOAD_BASE_DIR

FLOOR_IMAGE_SUBDIR = "floors"
FLOOR_IMAGE_EXT = ".webp"

# path -> (mtime_ns, size, fingerprint)
_FINGERPRINT_CACHE: dict[Path, tuple[int, int, str]] = {}


def floor_image_name(floor_id: str) -> str:
    """楼层 id 与文件名绑定:'floor-safety' -> 'safety'。楼层固定 6 个,不单独配置。"""
    return floor_id.removeprefix("floor-")


def file_fingerprint(path: Path) -> str | None:
    """文件内容 sha256 前 8 位;文件不存在返回 None。"""
    try:
        st = path.stat()
    except OSError:
        return None
    cached = _FINGERPRINT_CACHE.get(path)
    if cached and cached[0] == st.st_mtime_ns and cached[1] == st.st_size:
        return cached[2]
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    fingerprint = digest.hexdigest()[:8]
    _FINGERPRINT_CACHE[path] = (st.st_mtime_ns, st.st_size, fingerprint)
    return fingerprint


def floor_bg_image_url(floor_id: str, uploads_dir: Path = UPLOAD_BASE_DIR) -> str:
    """楼层背景图公开 URL(相对 API base),文件存在时带 ?v=<指纹>,缺图时不带版本号。"""
    name = floor_image_name(floor_id)
    rel = f"{settings.IMAGE_PATH_PREFIX}/{FLOOR_IMAGE_SUBDIR}/{name}{FLOOR_IMAGE_EXT}"
    fingerprint = file_fingerprint(uploads_dir / FLOOR_IMAGE_SUBDIR / f"{name}{FLOOR_IMAGE_EXT}")
    return f"{rel}?v={fingerprint}" if fingerprint else rel
