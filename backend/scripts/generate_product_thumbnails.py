"""存量商品图片缩略图补生脚本。

功能:
1. 压缩超尺寸 JPG/JPEG 原图到 800×800 JPEG q85（覆盖原文件）
2. 为每张原图生成 300×300 WebP 缩略图（_thumb.webp）

用法:
    # 预览（不执行）
    python scripts/generate_product_thumbnails.py --dry-run

    # 执行（默认 CPU 核数并发）
    python scripts/generate_product_thumbnails.py

    # 指定并发数
    python scripts/generate_product_thumbnails.py --workers 4

    # 只处理某个目录
    python scripts/generate_product_thumbnails.py --product-dir products/P-XFS-20740095

特性:
- 幂等：缩略图已存在自动跳过
- 断点续跑：中断后重跑安全
- 单张失败不中断，记录到 stderr
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from PIL import Image

# 与 _buyer_utils.py 保持一致
TARGET_SIZE = (800, 800)
JPEG_QUALITY = 85
THUMB_SIZE = (300, 300)
THUMB_WEBP_QUALITY = 80

UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _process_one(img_path: Path, dry_run: bool) -> dict:
    """处理单张图片，返回统计信息。"""
    result = {
        "path": str(img_path),
        "compressed": False,
        "thumb_generated": False,
        "thumb_skipped": False,
        "error": None,
        "saved_bytes": 0,
    }

    try:
        ext = img_path.suffix.lower()
        thumb_path = img_path.with_name(img_path.stem + "_thumb.webp")

        # 跳过已有缩略图
        if thumb_path.exists():
            result["thumb_skipped"] = True
        elif not dry_run:
            # 生成缩略图
            img = Image.open(img_path).convert("RGB")
            img.thumbnail(THUMB_SIZE, Image.LANCZOS)
            img.save(thumb_path, format="WEBP", quality=THUMB_WEBP_QUALITY)
            result["thumb_generated"] = True
        else:
            result["thumb_generated"] = True  # dry-run 标记为"会生成"

        # 压缩超尺寸 JPG/JPEG 原图
        if ext in {".jpg", ".jpeg"}:
            img = Image.open(img_path)
            if img.width > TARGET_SIZE[0] or img.height > TARGET_SIZE[1]:
                if not dry_run:
                    original_size = img_path.stat().st_size
                    img = img.convert("RGB")
                    img.thumbnail(TARGET_SIZE, Image.LANCZOS)
                    img.save(img_path, format="JPEG", quality=JPEG_QUALITY)
                    new_size = img_path.stat().st_size
                    result["saved_bytes"] = original_size - new_size
                result["compressed"] = True

    except Exception as e:
        result["error"] = str(e)

    return result


def _collect_images(base_dir: Path, product_dir: str | None) -> list[Path]:
    """收集需要处理的图片文件，排除已有的缩略图。"""
    if product_dir:
        scan_dir = base_dir / product_dir
    else:
        scan_dir = base_dir / "products"

    if not scan_dir.exists():
        print(f"[ERROR] 目录不存在: {scan_dir}", file=sys.stderr)
        sys.exit(1)

    images = []
    for p in scan_dir.rglob("*"):
        if p.suffix.lower() in IMAGE_EXTENSIONS and "_thumb" not in p.stem:
            images.append(p)
    return sorted(images)


def main() -> None:
    parser = argparse.ArgumentParser(description="商品图片缩略图补生脚本")
    parser.add_argument("--dry-run", action="store_true", help="只统计不执行")
    parser.add_argument("--workers", type=int, default=None, help="并发进程数（默认 CPU 核数）")
    parser.add_argument("--product-dir", type=str, default=None, help="只处理指定目录，如 products/P-XFS-123")
    args = parser.parse_args()

    images = _collect_images(UPLOADS_DIR, args.product_dir)
    total = len(images)

    if total == 0:
        print("[INFO] 没有需要处理的图片")
        return

    mode = "DRY-RUN" if args.dry_run else "EXECUTE"
    print(f"[{mode}] 共 {total} 张图片待处理")

    start = time.monotonic()
    stats = {"compressed": 0, "thumb_generated": 0, "thumb_skipped": 0, "errors": 0, "saved_bytes": 0}

    workers = args.workers
    # 单进程模式（图片少或调试时）
    if total <= 50 or workers == 1:
        for i, img_path in enumerate(images, 1):
            r = _process_one(img_path, args.dry_run)
            if r["error"]:
                stats["errors"] += 1
                print(f"[{i}/{total}] ERROR {r['path']}: {r['error']}", file=sys.stderr)
            else:
                if r["compressed"]:
                    stats["compressed"] += 1
                if r["thumb_generated"]:
                    stats["thumb_generated"] += 1
                if r["thumb_skipped"]:
                    stats["thumb_skipped"] += 1
                stats["saved_bytes"] += r["saved_bytes"]
            if i % 100 == 0 or i == total:
                print(f"[{i}/{total}] 进度 {i*100//total}%")
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_process_one, p, args.dry_run): p for p in images}
            done_count = 0
            for future in as_completed(futures):
                done_count += 1
                r = future.result()
                if r["error"]:
                    stats["errors"] += 1
                    print(f"[{done_count}/{total}] ERROR {r['path']}: {r['error']}", file=sys.stderr)
                else:
                    if r["compressed"]:
                        stats["compressed"] += 1
                    if r["thumb_generated"]:
                        stats["thumb_generated"] += 1
                    if r["thumb_skipped"]:
                        stats["thumb_skipped"] += 1
                    stats["saved_bytes"] += r["saved_bytes"]
                if done_count % 100 == 0 or done_count == total:
                    print(f"[{done_count}/{total}] 进度 {done_count*100//total}%")

    elapsed = time.monotonic() - start

    print(f"\n{'='*50}")
    print(f"[{mode}] 完成统计:")
    print(f"  总图片数:       {total}")
    print(f"  缩略图生成:     {stats['thumb_generated']}")
    print(f"  缩略图跳过:     {stats['thumb_skipped']}")
    print(f"  原图压缩:       {stats['compressed']}")
    print(f"  失败:           {stats['errors']}")
    if stats["saved_bytes"] > 0:
        print(f"  原图压缩节省:   {stats['saved_bytes'] / 1024 / 1024:.1f} MB")
    print(f"  耗时:           {elapsed:.1f}s")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
