"""add trigram indexes for product keyword search

Revision ID: 20260630_0010
Revises: 6b79e9ef98e2
Create Date: 2026-06-30 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260630_0010"
down_revision: Union[str, None] = "6b79e9ef98e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TRIGRAM_INDEXES: tuple[tuple[str, str], ...] = (
    ("ix_products_name_zh_trgm", "name_zh"),
    ("ix_products_name_en_trgm", "name_en"),
    ("ix_products_name_sw_trgm", "name_sw"),
    ("ix_products_brand_zh_trgm", "brand_zh"),
    ("ix_products_brand_en_trgm", "brand_en"),
    ("ix_products_manufacturer_model_trgm", "manufacturer_model"),
    ("ix_products_spu_code_trgm", "spu_code"),
)


def upgrade() -> None:
    context = op.get_context()
    if context.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    with context.autocommit_block():
        for index_name, column_name in TRIGRAM_INDEXES:
            op.execute(
                f"""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name}
                ON products USING gin ({column_name} gin_trgm_ops)
                WHERE deleted_at IS NULL
                """
            )


def downgrade() -> None:
    context = op.get_context()
    if context.dialect.name != "postgresql":
        return

    with context.autocommit_block():
        for index_name, _column_name in reversed(TRIGRAM_INDEXES):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {index_name}")
