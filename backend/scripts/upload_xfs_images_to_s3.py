#!/usr/bin/env python3
"""Upload XFS batch images to an S3-compatible bucket and write a manifest.

This script is intended to run on the machine that already holds the crawler
output directory, so hundreds of GB of images do not need to pass through the
application server.

Example:
    python scripts/upload_xfs_images_to_s3.py \
      --batch ../data/output_xfs_20260629_121951 \
      --bucket "$S3_BUCKET" \
      --endpoint-url "$S3_ENDPOINT_URL" \
      --access-key-id "$S3_ACCESS_KEY_ID" \
      --secret-access-key "$S3_SECRET_ACCESS_KEY" \
      --dry-run

Install dependencies on the upload machine:
    pip install boto3 pillow
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import sys
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any


SOURCE = "xfs"
DEFAULT_REGION = "gra"
THUMBNAIL_MAX_EDGE = 300
THUMBNAIL_QUALITY = 80


@dataclass(frozen=True)
class ImageItem:
    spu_code_raw: str
    platform_spu_code: str
    offer_path: Path
    local_path: Path
    rel_path: str
    source_url: str | None
    image_type: str
    object_key: str
    thumb_key: str | None
    sort_order: int


def platform_spu_code(raw_spu_code: str) -> str:
    """Generate the platform SPU code from the XFS SPU code."""
    digest = hashlib.sha256(f"P:XFS:{raw_spu_code}".encode()).hexdigest()[:12].upper()
    return f"MG-P{digest}"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def content_type_for(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def image_size(path: Path) -> tuple[int | None, int | None]:
    try:
        from PIL import Image
    except ImportError:
        return None, None

    try:
        with Image.open(path) as img:
            return img.width, img.height
    except Exception:
        return None, None


def make_thumbnail_bytes(path: Path) -> bytes:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required for --make-thumbnails: pip install pillow") from exc

    with Image.open(path) as img:
        img.thumbnail((THUMBNAIL_MAX_EDGE, THUMBNAIL_MAX_EDGE), Image.LANCZOS)
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        buf = BytesIO()
        img.save(buf, format="WEBP", quality=THUMBNAIL_QUALITY)
        return buf.getvalue()


def object_ext(path: Path) -> str:
    suffix = path.suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"} else ".jpg"


def clean_filename(path: Path) -> str:
    stem = path.stem.replace(" ", "_")
    return f"{stem}{object_ext(path)}"


def iter_offer_paths(batch_dir: Path) -> list[Path]:
    return sorted(batch_dir.glob("categories/**/offers/*/offer.json"))


def build_image_items(batch_dir: Path) -> list[ImageItem]:
    items: list[ImageItem] = []

    for offer_path in iter_offer_paths(batch_dir):
        offer = read_json(offer_path)
        raw_spu = str(offer.get("spuCode") or offer_path.parent.name).strip()
        if not raw_spu:
            continue
        platform_spu = platform_spu_code(raw_spu)
        offer_dir = offer_path.parent

        regular_images = offer.get("images") or []
        sorted_regular = sorted(
            enumerate(regular_images),
            key=lambda pair: int((pair[1] or {}).get("sort") or pair[0]),
        )

        for position, (idx, img_def) in enumerate(sorted_regular):
            if not isinstance(img_def, dict):
                continue
            rel_path = str(img_def.get("path") or "").strip()
            if not rel_path:
                continue

            local_path = offer_dir / rel_path
            filename = clean_filename(local_path)
            folder = "main" if position == 0 else "gallery"
            image_type = "MAIN" if position == 0 else "GALLERY"
            object_key = f"products/{SOURCE}/{platform_spu}/{folder}/{filename}"
            thumb_stem = Path(filename).stem
            thumb_key = f"products/{SOURCE}/{platform_spu}/{folder}/{thumb_stem}_thumb.webp"

            items.append(ImageItem(
                spu_code_raw=raw_spu,
                platform_spu_code=platform_spu,
                offer_path=offer_path,
                local_path=local_path,
                rel_path=rel_path,
                source_url=img_def.get("sourceUrl") or None,
                image_type=image_type,
                object_key=object_key,
                thumb_key=thumb_key,
                sort_order=int(img_def.get("sort") or idx),
            ))

        for idx, img_def in enumerate(offer.get("detailImages") or []):
            if not isinstance(img_def, dict):
                continue
            rel_path = str(img_def.get("path") or "").strip()
            if not rel_path:
                continue

            local_path = offer_dir / rel_path
            filename = clean_filename(local_path)
            object_key = f"products/{SOURCE}/{platform_spu}/detail/{filename}"
            thumb_stem = Path(filename).stem
            thumb_key = f"products/{SOURCE}/{platform_spu}/detail/{thumb_stem}_thumb.webp"

            items.append(ImageItem(
                spu_code_raw=raw_spu,
                platform_spu_code=platform_spu,
                offer_path=offer_path,
                local_path=local_path,
                rel_path=rel_path,
                source_url=img_def.get("sourceUrl") or None,
                image_type="DETAIL",
                object_key=object_key,
                thumb_key=thumb_key,
                sort_order=idx,
            ))

    return items


def create_s3_client(args: argparse.Namespace):
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("boto3 is required for uploads: pip install boto3") from exc

    return boto3.client(
        "s3",
        endpoint_url=args.endpoint_url,
        aws_access_key_id=args.access_key_id,
        aws_secret_access_key=args.secret_access_key,
        region_name=args.region,
    )


def s3_exists(client, bucket: str, key: str) -> bool:
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def upload_file(client, bucket: str, key: str, path: Path) -> None:
    client.upload_file(
        str(path),
        bucket,
        key,
        ExtraArgs={
            "ContentType": content_type_for(path),
            "CacheControl": "public, max-age=31536000, immutable",
        },
    )


def upload_thumbnail(client, bucket: str, key: str, src_path: Path) -> int:
    body = make_thumbnail_bytes(src_path)
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType="image/webp",
        CacheControl="public, max-age=31536000, immutable",
    )
    return len(body)


def manifest_record(
    item: ImageItem,
    *,
    batch_dir: Path,
    status: str,
    width: int | None,
    height: int | None,
    file_size: int | None,
    thumb_size: int | None,
    error: str | None = None,
) -> dict[str, Any]:
    try:
        local_rel = str(item.local_path.relative_to(batch_dir))
        offer_rel = str(item.offer_path.relative_to(batch_dir))
    except ValueError:
        local_rel = str(item.local_path)
        offer_rel = str(item.offer_path)

    record: dict[str, Any] = {
        "spuCode": item.spu_code_raw,
        "platformSpuCode": item.platform_spu_code,
        "imageType": item.image_type,
        "sortOrder": item.sort_order,
        "offerPath": offer_rel,
        "localPath": local_rel,
        "sourceUrl": item.source_url,
        "objectKey": item.object_key,
        "thumbKey": item.thumb_key,
        "width": width,
        "height": height,
        "fileSize": file_size,
        "contentType": content_type_for(item.local_path),
        "thumbSize": thumb_size,
        "status": status,
    }
    if error:
        record["error"] = error
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload XFS batch images to S3 and write s3_manifest.jsonl")
    parser.add_argument("--batch", type=Path, required=True, help="XFS output_xfs_xxx batch directory")
    parser.add_argument("--manifest", type=Path, default=None, help="Output manifest path. Defaults to <batch>/s3_manifest.jsonl")
    parser.add_argument("--bucket", default=os.getenv("S3_BUCKET"), help="S3 bucket name")
    parser.add_argument("--endpoint-url", default=os.getenv("S3_ENDPOINT_URL"), help="S3 endpoint URL")
    parser.add_argument("--access-key-id", default=os.getenv("S3_ACCESS_KEY_ID"), help="S3 access key")
    parser.add_argument("--secret-access-key", default=os.getenv("S3_SECRET_ACCESS_KEY"), help="S3 secret key")
    parser.add_argument("--region", default=os.getenv("S3_REGION", DEFAULT_REGION), help="S3 region")
    parser.add_argument("--dry-run", action="store_true", help="Do not upload, only scan and write manifest")
    parser.add_argument("--skip-existing", action="store_true", help="Skip upload when object already exists")
    parser.add_argument(
        "--make-thumbnails",
        action="store_true",
        help="Generate and upload 300px max-edge WebP thumbnails for all images",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    args.batch = args.batch.resolve()
    if not args.batch.is_dir():
        raise SystemExit(f"Batch directory not found: {args.batch}")
    if args.manifest is None:
        args.manifest = args.batch / "s3_manifest.jsonl"
    if not args.dry_run:
        missing = [
            name for name in ("bucket", "endpoint_url", "access_key_id", "secret_access_key")
            if not getattr(args, name)
        ]
        if missing:
            raise SystemExit(f"Missing required S3 config for upload: {', '.join(missing)}")


def main() -> None:
    args = parse_args()
    validate_args(args)

    items = build_image_items(args.batch)
    print(f"[scan] batch={args.batch}")
    print(f"[scan] images={len(items)}")
    print(f"[manifest] {args.manifest}")

    client = None if args.dry_run else create_s3_client(args)

    ok = 0
    failed = 0
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    with args.manifest.open("w", encoding="utf-8") as manifest:
        for idx, item in enumerate(items, 1):
            width, height = image_size(item.local_path) if item.local_path.exists() else (None, None)
            file_size = item.local_path.stat().st_size if item.local_path.exists() else None
            thumb_size: int | None = None

            try:
                if not item.local_path.is_file():
                    raise FileNotFoundError(f"Local image not found: {item.local_path}")

                status = "dry_run"
                if not args.dry_run:
                    if args.skip_existing and s3_exists(client, args.bucket, item.object_key):
                        status = "exists"
                    else:
                        upload_file(client, args.bucket, item.object_key, item.local_path)
                        status = "uploaded"

                    if args.make_thumbnails and item.thumb_key:
                        if args.skip_existing and s3_exists(client, args.bucket, item.thumb_key):
                            pass
                        else:
                            thumb_size = upload_thumbnail(client, args.bucket, item.thumb_key, item.local_path)

                record = manifest_record(
                    item,
                    batch_dir=args.batch,
                    status=status,
                    width=width,
                    height=height,
                    file_size=file_size,
                    thumb_size=thumb_size,
                )
                ok += 1
            except Exception as exc:
                record = manifest_record(
                    item,
                    batch_dir=args.batch,
                    status="failed",
                    width=width,
                    height=height,
                    file_size=file_size,
                    thumb_size=thumb_size,
                    error=str(exc),
                )
                failed += 1

            manifest.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

            if idx % 100 == 0:
                print(f"[progress] {idx}/{len(items)} ok={ok} failed={failed}")

    print(f"[done] ok={ok} failed={failed} manifest={args.manifest}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
