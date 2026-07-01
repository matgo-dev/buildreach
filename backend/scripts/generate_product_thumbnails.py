"""存量商品图片缩略图补生脚本。

功能:
1. 压缩超尺寸 JPG/JPEG 原图到 800×800 JPEG q85（覆盖原文件）
2. 为每张原图生成 300×300 WebP 缩略图（_thumb.webp）

用法:
    # 预览（不执行）
    python scripts/generate_product_thumbnails.py --dry-run

    # 执行（默认最多 4 进程并发）
    python scripts/generate_product_thumbnails.py

    # 指定并发数
    python scripts/generate_product_thumbnails.py --workers 4

    # 指定最多排队任务数
    python scripts/generate_product_thumbnails.py --workers 4 --queue-size 32

    # 只处理某个目录
    python scripts/generate_product_thumbnails.py --product-dir products/P-XFS-20740095

特性:
- 幂等：缩略图已存在自动跳过
- 断点续跑：中断后重跑安全
- 单张失败不中断，记录到 stderr
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from PIL import Image

# 与 _buyer_utils.py 保持一致
TARGET_SIZE = (800, 800)
JPEG_QUALITY = 85
THUMB_SIZE = (300, 300)
THUMB_WEBP_QUALITY = 80
DEFAULT_MAX_WORKERS = 4
QUEUE_MULTIPLIER = 8

UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _thumb_is_fresh(img_path: Path, thumb_path: Path) -> bool:
    """缩略图存在且不早于原图时视为有效。"""
    try:
        return (
            thumb_path.exists()
            and thumb_path.stat().st_size > 0
            and thumb_path.stat().st_mtime >= img_path.stat().st_mtime
        )
    except OSError:
        return False


def _atomic_save(img: Image.Image, dest_path: Path, fmt: str, **save_kwargs) -> None:
    """先写临时文件，成功后原子替换目标文件。"""
    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=dest_path.parent,
            prefix=f".{dest_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_name = tmp.name
        tmp_path = Path(tmp_name)
        img.save(tmp_path, format=fmt, **save_kwargs)
        tmp_path.replace(dest_path)
    except Exception:
        if tmp_name:
            Path(tmp_name).unlink(missing_ok=True)
        raise


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
        thumb_fresh = _thumb_is_fresh(img_path, thumb_path)

        if thumb_fresh and ext not in {".jpg", ".jpeg"}:
            result["thumb_skipped"] = True
            return result

        with Image.open(img_path) as opened:
            needs_compress = (
                ext in {".jpg", ".jpeg"}
                and (opened.width > TARGET_SIZE[0] or opened.height > TARGET_SIZE[1])
            )
            needs_thumb = not thumb_fresh or needs_compress

            if not needs_compress and not needs_thumb:
                if thumb_fresh:
                    result["thumb_skipped"] = True
                return result

            if dry_run:
                result["compressed"] = needs_compress
                result["thumb_generated"] = needs_thumb
                return result

            working = opened.convert("RGB")

        # 压缩原图会改变源文件内容，因此先压缩，再基于压缩后的图生成缩略图。
        if needs_compress:
            original_size = img_path.stat().st_size
            working.thumbnail(TARGET_SIZE, Image.LANCZOS)
            _atomic_save(working, img_path, "JPEG", quality=JPEG_QUALITY)
            new_size = img_path.stat().st_size
            result["saved_bytes"] = original_size - new_size
            result["compressed"] = True

        if needs_thumb:
            thumb = working.copy()
            thumb.thumbnail(THUMB_SIZE, Image.LANCZOS)
            _atomic_save(thumb, thumb_path, "WEBP", quality=THUMB_WEBP_QUALITY)
            result["thumb_generated"] = True

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
    parser.add_argument("--workers", type=int, default=None, help=f"并发进程数（默认最多 {DEFAULT_MAX_WORKERS}）")
    parser.add_argument("--queue-size", type=int, default=None, help="最多排队任务数（默认 workers * 8）")
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

    workers = args.workers or min(os.cpu_count() or 1, DEFAULT_MAX_WORKERS)
    workers = max(1, workers)
    queue_size = args.queue_size or workers * QUEUE_MULTIPLIER
    queue_size = max(workers, queue_size)

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
        pending = set()
        image_iter = iter(images)
        done_count = 0

        with ProcessPoolExecutor(max_workers=workers) as pool:
            def submit_until_full() -> None:
                while len(pending) < queue_size:
                    try:
                        p = next(image_iter)
                    except StopIteration:
                        return
                    pending.add(pool.submit(_process_one, p, args.dry_run))

            submit_until_full()
            while pending:
                for future in as_completed(pending):
                    pending.remove(future)
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
                    submit_until_full()
                    break

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
