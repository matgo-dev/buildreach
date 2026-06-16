"""simplify_line_type — PRODUCT/FEE 二分法

RESPONSE/ALTERNATIVE → PRODUCT, ADDITIONAL/SERVICE → FEE, SKIPPED 行软删.

Revision ID: 0535dd9a4db5
Revises: 13157bccfd7e
Create Date: 2026-06-16
"""
from typing import Sequence, Union
from alembic import op


revision: str = '0535dd9a4db5'
down_revision: Union[str, None] = '13157bccfd7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        UPDATE rfq_quote_items
        SET line_type = 'PRODUCT'
        WHERE line_type IN ('RESPONSE', 'ALTERNATIVE')
    """)
    op.execute("""
        UPDATE rfq_quote_items
        SET line_type = 'FEE'
        WHERE line_type IN ('ADDITIONAL', 'SERVICE')
    """)
    # SKIPPED 行软删
    op.execute("""
        UPDATE rfq_quote_items
        SET deleted_at = NOW()
        WHERE line_type = 'SKIPPED' AND deleted_at IS NULL
    """)
    op.execute("""
        UPDATE rfq_quote_items
        SET line_type = 'PRODUCT'
        WHERE line_type = 'SKIPPED'
    """)
    op.alter_column('rfq_quote_items', 'line_type', server_default='PRODUCT')


def downgrade() -> None:
    op.alter_column('rfq_quote_items', 'line_type', server_default='RESPONSE')
    op.execute("""
        UPDATE rfq_quote_items
        SET line_type = 'RESPONSE'
        WHERE line_type = 'PRODUCT'
    """)
    op.execute("""
        UPDATE rfq_quote_items
        SET line_type = 'ADDITIONAL'
        WHERE line_type = 'FEE'
    """)
