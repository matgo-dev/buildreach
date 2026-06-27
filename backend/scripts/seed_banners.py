"""轮播图初始化 seed 脚本。

扫描 /app/uploads/banners/ 下的图片文件，往 banner_slides 表 upsert 记录。
幂等：按 image_url 匹配，已存在则跳过。

用法
----
    python scripts/seed_banners.py
    python scripts/seed_banners.py --dry-run
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.db.base import _utcnow  # noqa: E402
from app.db.models.banner_slide import BannerSlide  # noqa: E402
from app.db.url import prepare_sync_url  # noqa: E402

log = logging.getLogger(__name__)

UPLOADS_DIR = Path("/app/uploads/banners")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

# 图片文件名 → 中英文标题映射（人工维护）
BANNER_META: dict[str, dict] = {
    "banner-construction": {
        "title_zh": "东非建材供应链平台",
        "title_en": "East Africa Construction Supply Chain",
        "title_sw": "Jukwaa la Ugavi wa Ujenzi Afrika Mashariki",
        "sort_order": 1,
    },
    "banner-crane": {
        "title_zh": "一站式建材采购",
        "title_en": "One-Stop Construction Procurement",
        "title_sw": "Ununuzi wa Ujenzi Sehemu Moja",
        "sort_order": 2,
    },
    "banner-skyline": {
        "title_zh": "连接中国供应商与东非买家",
        "title_en": "Connecting Chinese Suppliers with East African Buyers",
        "title_sw": "Kuunganisha Wauzaji wa China na Wanunuzi wa Afrika Mashariki",
        "sort_order": 3,
    },
}


def _image_key(filename: str) -> str:
    """返回相对路径，不含域名/端口，API 层动态拼 IMAGE_PATH_PREFIX。"""
    return f"uploads/banners/{filename}"


def seed_banners(db: Session, *, dry_run: bool = False) -> int:
    """扫描图片文件，upsert banner_slides 记录。"""
    if not UPLOADS_DIR.exists():
        log.warning("轮播图目录不存在: %s", UPLOADS_DIR)
        return 0

    images = sorted(
        f for f in UPLOADS_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    )

    if not images:
        log.warning("未找到图片文件: %s", UPLOADS_DIR)
        return 0

    log.info("发现 %d 张图片", len(images))

    # 查询已有记录（按相对路径匹配）
    existing_keys: set[str] = set()
    for row in db.execute(select(BannerSlide.image_url)).scalars().all():
        existing_keys.add(row)

    inserted = 0
    skipped = 0

    for img in images:
        key = _image_key(img.name)
        if key in existing_keys:
            log.info("  跳过(已存在): %s", img.name)
            skipped += 1
            continue

        stem = img.stem  # 去掉扩展名
        meta = BANNER_META.get(stem, {})

        if dry_run:
            log.info("  [DRY RUN] 将插入: %s → %s", img.name, meta.get("title_zh", "(无标题)"))
            inserted += 1
            continue

        now = _utcnow()
        banner = BannerSlide(
            title_zh=meta.get("title_zh"),
            title_en=meta.get("title_en"),
            title_sw=meta.get("title_sw"),
            image_url=key,
            link_url=None,
            sort_order=meta.get("sort_order", 99),
            is_active=True,
            position="home_carousel",
            source_lang="zh",
            trans_meta={
                "title_zh": "src",
                "title_en": "manual" if meta.get("title_en") else "pending",
                "title_sw": "manual" if meta.get("title_sw") else "pending",
            },
            created_at=now,
            updated_at=now,
        )
        db.add(banner)
        inserted += 1
        log.info("  插入: %s → %s", img.name, meta.get("title_zh", "(无标题)"))

    if not dry_run:
        db.flush()

    log.info("完成: 新增=%d, 跳过=%d", inserted, skipped)
    return inserted


def main():
    parser = argparse.ArgumentParser(description="轮播图初始化 seed")
    parser.add_argument("--dry-run", action="store_true", help="只预检不写库")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    sync_url = prepare_sync_url(str(settings.DATABASE_URL))
    engine = create_engine(sync_url, echo=False)

    with Session(engine) as db:
        seed_banners(db, dry_run=args.dry_run)
        if not args.dry_run:
            db.commit()
            log.info("事务已提交")


if __name__ == "__main__":
    main()
