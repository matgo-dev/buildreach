"""banner image_url 改为相对路径存储

Revision ID: a84ca1ab6928
Revises: fe438ffd1696
Create Date: 2026-06-26
"""
from typing import Union

from alembic import op

revision: str = 'a84ca1ab6928'
down_revision = ('6aa11955310e', 'b3c4d5e6f7g8', 'a3f8e1b20614', '8c6363c79f45')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 去掉已有记录中的绝对 URL 前缀，只保留 uploads/banners/... 相对路径
    # 兼容各种环境的前缀：http://xxx/static/uploads/... → uploads/...
    op.execute("""
        UPDATE banner_slides
        SET image_url = regexp_replace(image_url, '^https?://[^/]+/static/', '')
        WHERE image_url LIKE 'http://%' OR image_url LIKE 'https://%'
    """)


def downgrade() -> None:
    # 无法精确还原原始域名，不做回退
    pass
