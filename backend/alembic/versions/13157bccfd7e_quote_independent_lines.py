"""quote_independent_lines — 报价行独立化(方案B)

rfq_item_id → source_rfq_item_id (nullable), 新增 line_type 和商品快照列,
删旧 1:1 唯一约束, 回填已有数据.

Revision ID: 13157bccfd7e
Revises: 7e858d97bff2
Create Date: 2026-06-16 14:56:57.937976
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '13157bccfd7e'
down_revision: Union[str, None] = '7e858d97bff2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. rfq_item_id 改名 source_rfq_item_id + 改可空
    op.alter_column(
        'rfq_quote_items', 'rfq_item_id',
        new_column_name='source_rfq_item_id',
        nullable=True,
    )

    # 2. 新增 line_type
    op.add_column('rfq_quote_items', sa.Column(
        'line_type', sa.String(20), nullable=False, server_default='RESPONSE',
    ))

    # 3. 新增商品快照列
    op.add_column('rfq_quote_items', sa.Column(
        'product_id', sa.Integer(), nullable=True,
    ))
    op.create_foreign_key(
        'fk_rfq_quote_items_product_id', 'rfq_quote_items', 'products',
        ['product_id'], ['id'],
    )
    op.add_column('rfq_quote_items', sa.Column(
        'product_name_snapshot', sa.String(200), nullable=True,
    ))
    op.add_column('rfq_quote_items', sa.Column(
        'quoted_variants', sa.JSON(), nullable=True,
    ))
    op.add_column('rfq_quote_items', sa.Column(
        'variant_display', sa.String(500), nullable=True,
    ))
    op.add_column('rfq_quote_items', sa.Column(
        'quantity', sa.Numeric(18, 3), nullable=True,
    ))
    op.add_column('rfq_quote_items', sa.Column(
        'uom', sa.String(20), nullable=True,
    ))

    # 4. 回填已有数据
    op.execute("""
        UPDATE rfq_quote_items qi
        SET
            product_id = ri.product_id,
            product_name_snapshot = COALESCE(ri.product_name_snapshot_zh, ri.product_name_snapshot_en),
            quoted_variants = ri.variant_snapshot,
            quantity = ri.quantity,
            uom = ri.uom_snapshot,
            line_type = CASE WHEN qi.skipped THEN 'SKIPPED' ELSE 'RESPONSE' END
        FROM rfq_items ri
        WHERE qi.source_rfq_item_id = ri.id
    """)

    # 5. 新增索引
    op.create_index(
        'ix_rfq_quote_items_source_rfq_item_id',
        'rfq_quote_items', ['source_rfq_item_id'],
    )

    # 6. 删旧 1:1 唯一约束
    op.drop_constraint(
        'uq_rfq_quote_items_quote_rfq_item',
        'rfq_quote_items', type_='unique',
    )


def downgrade() -> None:
    # 恢复唯一约束
    op.create_unique_constraint(
        'uq_rfq_quote_items_quote_rfq_item', 'rfq_quote_items',
        ['quote_id', 'source_rfq_item_id'],
    )

    op.drop_index('ix_rfq_quote_items_source_rfq_item_id', table_name='rfq_quote_items')

    op.drop_column('rfq_quote_items', 'uom')
    op.drop_column('rfq_quote_items', 'quantity')
    op.drop_column('rfq_quote_items', 'variant_display')
    op.drop_column('rfq_quote_items', 'quoted_variants')
    op.drop_column('rfq_quote_items', 'product_name_snapshot')
    op.drop_constraint('fk_rfq_quote_items_product_id', 'rfq_quote_items', type_='foreignkey')
    op.drop_column('rfq_quote_items', 'product_id')
    op.drop_column('rfq_quote_items', 'line_type')

    # source_rfq_item_id 改回 rfq_item_id + NOT NULL
    op.alter_column(
        'rfq_quote_items', 'source_rfq_item_id',
        new_column_name='rfq_item_id',
        nullable=False,
    )
