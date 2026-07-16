"""楼层背景图初始化 — 把 data/floors 拷进 uploads/floors 卷。

楼层图数量/文件名固定(跟一级类目绑定),前端硬编码 6 个稳定 URL
`/static/floors/xxx.webp`(后端 serve uploads 卷)。图片内容偶尔换 → 换图只需
替换 uploads/floors/ 下同名文件,免部署;不上 DB。

本脚本幂等:目标已存在同名文件则跳过(不覆盖,避免盖掉线上换过的新图)。

用法(本地)
----
    python scripts/seed_floors.py
    python scripts/seed_floors.py --force   # 覆盖已存在文件

生产上线(后端容器内无 repo data/floors,直接从宿主机拷进卷):
    docker compose -f docker-compose.production.yml cp data/floors/. backend:/app/uploads/floors/
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))

from app.services._buyer_utils import UPLOAD_BASE_DIR  # noqa: E402

log = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".webp", ".png", ".jpg", ".jpeg"}
SOURCE_DIR = _BACKEND_ROOT.parent / "data" / "floors"
TARGET_DIR = Path(UPLOAD_BASE_DIR) / "floors"


def seed_floors(*, force: bool = False) -> int:
    if not SOURCE_DIR.is_dir():
        log.warning("图源目录不存在: %s", SOURCE_DIR)
        return 0

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    copied = 0
    for f in sorted(SOURCE_DIR.iterdir()):
        if not (f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS):
            continue
        dst = TARGET_DIR / f.name
        if dst.exists() and not force:
            log.info("  跳过(已存在): %s", f.name)
            continue
        shutil.copy2(f, dst)
        copied += 1
        log.info("  拷贝: %s", f.name)

    log.info("完成: 拷贝 %d 张到 %s", copied, TARGET_DIR)
    return copied


def main():
    parser = argparse.ArgumentParser(description="楼层背景图初始化")
    parser.add_argument("--force", action="store_true", help="覆盖已存在文件")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    seed_floors(force=args.force)


if __name__ == "__main__":
    main()
