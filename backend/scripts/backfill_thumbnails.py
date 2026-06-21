"""一次性脚本 — 为已有图片附件补生成缩略图。

用法(ECS 容器内):
    docker compose exec backend python scripts/backfill_thumbnails.py

用法(本地开发):
    python scripts/backfill_thumbnails.py
"""
from __future__ import annotations

import os
import sys
import uuid
from io import BytesIO
from pathlib import Path

import psycopg
from PIL import Image

# 复用 attachment service 的缩略图参数
THUMBNAIL_MAX_EDGE = 300
THUMBNAIL_QUALITY = 80

# 私有附件存储目录
PRIVATE_UPLOADS_DIR = Path(__file__).resolve().parent.parent / "private_uploads" / "attachments"


def _db_url() -> str:
    """从 DATABASE_URL 转为 psycopg 同步连接串。"""
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("[backfill] ERROR: DATABASE_URL 未设置")
        sys.exit(1)
    # postgresql+asyncpg://... → postgresql://...
    return url.replace("postgresql+asyncpg", "postgresql")


def main() -> None:
    conn = psycopg.connect(_db_url())
    cur = conn.cursor()

    cur.execute("""
        SELECT id, file_key, content_type
        FROM attachments
        WHERE thumbnail_key IS NULL
          AND content_type LIKE 'image/%%'
          AND deleted_at IS NULL
        ORDER BY id
    """)
    rows = cur.fetchall()

    if not rows:
        print("[backfill] 无需补生成的图片附件")
        return

    print(f"[backfill] 共 {len(rows)} 个图片附件需补生成缩略图")

    success = 0
    for idx, (att_id, file_key, content_type) in enumerate(rows, 1):
        src_path = PRIVATE_UPLOADS_DIR / Path(file_key).name
        if not src_path.is_file():
            print(f"[{idx}/{len(rows)}] attachment_id={att_id} 原图文件缺失: {file_key}, 跳过")
            continue

        try:
            img = Image.open(src_path)
            img.thumbnail((THUMBNAIL_MAX_EDGE, THUMBNAIL_MAX_EDGE), Image.LANCZOS)
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=THUMBNAIL_QUALITY, optimize=True)
            thumb_bytes = buf.getvalue()

            thumbnail_key = f"thumbnail_{uuid.uuid4().hex}.jpg"
            dest_path = PRIVATE_UPLOADS_DIR / thumbnail_key
            dest_path.write_bytes(thumb_bytes)

            cur.execute(
                """
                UPDATE attachments
                SET thumbnail_key = %s,
                    thumbnail_content_type = 'image/jpeg',
                    thumbnail_size_bytes = %s
                WHERE id = %s
                """,
                (thumbnail_key, len(thumb_bytes), att_id),
            )
            conn.commit()
            success += 1
            print(f"[{idx}/{len(rows)}] attachment_id={att_id} → {thumbnail_key} ({len(thumb_bytes)} bytes)")

        except Exception as e:
            conn.rollback()
            print(f"[{idx}/{len(rows)}] attachment_id={att_id} 失败: {e}")

    print(f"[backfill] 完成: {success}/{len(rows)} 成功")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
