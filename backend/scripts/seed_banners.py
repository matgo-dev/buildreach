"""轮播图初始化 seed 脚本。

把现有轮播图收敛到 uploads 卷,并往 banner_slides 表 upsert 记录:

1. 从图源目录(容器 /srv/banners,本地 frontend/public/banners)拷贝图片到
   uploads/banners/(若目标已存在同名文件则跳过,不覆盖)。
2. 扫描 uploads/banners/,每个图片 upsert 一条 banner_slide。
   image_url 存相对 key `banners/{filename}`,公开 API 拼 IMAGE_PATH_PREFIX → /static/banners/xxx。
3. 幂等:按 image_url 匹配,已存在则跳过。

--purge-legacy 会删除 home_carousel 位下 image_url 不以 `banners/` 开头的旧记录
(历史遗留的 `/banners/xxx.png` 绝对路径,图片已不存在)。

用法
----
    python scripts/seed_banners.py --dry-run
    python scripts/seed_banners.py
    python scripts/seed_banners.py --purge-legacy
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.db.base import _utcnow  # noqa: E402
from app.db.models.banner_slide import BannerSlide  # noqa: E402
from app.db.url import prepare_sync_url  # noqa: E402
from app.services._buyer_utils import UPLOAD_BASE_DIR  # noqa: E402

log = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

# 目标目录(uploads 卷内),公开 API 走 /static/banners/ 命中此处
TARGET_DIR = Path(UPLOAD_BASE_DIR) / "banners"

# 图源候选:容器内挂载卷优先,回退本地 public/banners
SOURCE_CANDIDATES = [
    Path("/srv/banners"),
    _BACKEND_ROOT.parent / "frontend" / "public" / "banners",
]

# 文件名 stem → 标题(仅主图给文案,工厂实拍图留空由运营后台按需补)
BANNER_META: dict[str, dict] = {
    "hero-main": {
        "title_zh": "东非建材供应链平台",
        "title_en": "East Africa Construction Supply Chain",
        "title_sw": "Jukwaa la Ugavi wa Ujenzi Afrika Mashariki",
    },
}


def _image_key(filename: str) -> str:
    """相对 uploads 根的 key,不含域名/前缀,API 层拼 IMAGE_PATH_PREFIX。"""
    return f"banners/{filename}"


def _sort_order(stem: str, index: int) -> int:
    """hero-main 排第一,其余按扫描顺序 1..N。"""
    return 0 if stem == "hero-main" else index + 1


def _copy_source_images() -> None:
    """从图源拷贝图片到 uploads/banners/(不覆盖同名)。"""
    source = next((d for d in SOURCE_CANDIDATES if d.is_dir()), None)
    if source is None:
        log.warning("未找到图源目录(尝试过 %s),跳过拷贝", SOURCE_CANDIDATES)
        return

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    copied = 0
    for f in sorted(source.iterdir()):
        if not (f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS):
            continue
        dst = TARGET_DIR / f.name
        if dst.exists():
            continue
        shutil.copy2(f, dst)
        copied += 1
    log.info("从 %s 拷贝 %d 张新图到 %s", source, copied, TARGET_DIR)


def _purge_legacy(db: Session, *, dry_run: bool) -> int:
    """删除 home_carousel 位下非 banners/ 前缀的历史废记录。"""
    stmt = select(BannerSlide).where(
        BannerSlide.position == "home_carousel",
        ~BannerSlide.image_url.like("banners/%"),
    )
    legacy = db.execute(stmt).scalars().all()
    for row in legacy:
        log.info("  [purge] 删除废记录 id=%s image_url=%s", row.id, row.image_url)
    if not dry_run and legacy:
        db.execute(
            delete(BannerSlide).where(
                BannerSlide.id.in_([r.id for r in legacy])
            )
        )
    return len(legacy)


def seed_banners(db: Session, *, dry_run: bool = False, purge_legacy: bool = False) -> int:
    """拷图 + 扫描 + upsert banner_slides。"""
    if purge_legacy:
        removed = _purge_legacy(db, dry_run=dry_run)
        log.info("清理历史废记录: %d 条", removed)

    if not dry_run:
        _copy_source_images()

    if not TARGET_DIR.is_dir():
        log.warning("轮播图目录不存在: %s", TARGET_DIR)
        return 0

    images = sorted(
        f for f in TARGET_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not images:
        log.warning("未找到图片文件: %s", TARGET_DIR)
        return 0

    log.info("发现 %d 张图片", len(images))

    existing_keys = set(db.execute(select(BannerSlide.image_url)).scalars().all())

    inserted = 0
    skipped = 0
    for index, img in enumerate(images):
        key = _image_key(img.name)
        if key in existing_keys:
            log.info("  跳过(已存在): %s", img.name)
            skipped += 1
            continue

        meta = BANNER_META.get(img.stem, {})
        if dry_run:
            log.info("  [DRY RUN] 将插入: %s → %s", img.name, meta.get("title_zh", "(无标题)"))
            inserted += 1
            continue

        now = _utcnow()
        db.add(BannerSlide(
            title_zh=meta.get("title_zh"),
            title_en=meta.get("title_en"),
            title_sw=meta.get("title_sw"),
            image_url=key,
            link_url=None,
            sort_order=_sort_order(img.stem, index),
            is_active=True,
            position="home_carousel",
            source_lang="zh",
            trans_meta={
                "title_zh": "src" if meta.get("title_zh") else "pending",
                "title_en": "manual" if meta.get("title_en") else "pending",
                "title_sw": "manual" if meta.get("title_sw") else "pending",
            },
            created_at=now,
            updated_at=now,
        ))
        inserted += 1
        log.info("  插入: %s → %s", img.name, meta.get("title_zh", "(无标题)"))

    if not dry_run:
        db.flush()

    log.info("完成: 新增=%d, 跳过=%d", inserted, skipped)
    return inserted


def main():
    parser = argparse.ArgumentParser(description="轮播图初始化 seed")
    parser.add_argument("--dry-run", action="store_true", help="只预检不写库/不拷图")
    parser.add_argument(
        "--purge-legacy", action="store_true",
        help="删除 home_carousel 位下非 banners/ 前缀的历史废记录",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    sync_url = prepare_sync_url(str(settings.DATABASE_URL))
    engine = create_engine(sync_url, echo=False)

    with Session(engine) as db:
        seed_banners(db, dry_run=args.dry_run, purge_legacy=args.purge_legacy)
        if not args.dry_run:
            db.commit()
            log.info("事务已提交")


if __name__ == "__main__":
    main()
