"""i18n: Category 加 I18nMixin, ProductAttr rename + 加 sw 列 + I18nMixin

Category:
  - 新增 source_lang, trans_meta, i18n_pending_at
  - 数据补丁:现有行初始化翻译状态

ProductAttr:
  - rename attr_key → attr_key_en, attr_value → attr_value_en
  - 新增 attr_key_sw, attr_value_sw
  - 新增 source_lang, trans_meta, i18n_pending_at
  - 重建唯一索引(列名变了)
  - 数据补丁:现有行初始化翻译状态

[allow-destructive-migration]

Revision ID: a3f8e1b20614
Revises: 1220b76561ab
Create Date: 2026-06-14
"""
from alembic import op
import sqlalchemy as sa

revision = "a3f8e1b20614"
down_revision = "1220b76561ab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ===================== Category: 加 I18nMixin 列 =====================
    op.add_column("categories", sa.Column(
        "source_lang", sa.String(10), nullable=False, server_default="zh",
    ))
    op.add_column("categories", sa.Column(
        "trans_meta", sa.JSON(), nullable=False, server_default="{}",
    ))
    op.add_column("categories", sa.Column(
        "i18n_pending_at", sa.DateTime(), nullable=True,
    ))
    op.create_index("ix_categories_i18n_pending_at", "categories", ["i18n_pending_at"])

    # 数据补丁:根据 name_en/name_sw 非空情况初始化 trans_meta
    op.execute("""
        UPDATE categories SET
            trans_meta = jsonb_build_object(
                'name_zh', 'src',
                'name_en', CASE WHEN name_en IS NOT NULL AND name_en != '' THEN 'manual' ELSE 'pending' END,
                'name_sw', CASE WHEN name_sw IS NOT NULL AND name_sw != '' THEN 'manual' ELSE 'pending' END
            ),
            i18n_pending_at = CASE
                WHEN (name_en IS NULL OR name_en = '' OR name_sw IS NULL OR name_sw = '')
                THEN NOW()
                ELSE NULL
            END
    """)

    # ===================== ProductAttr: rename + 加列 =====================

    # 1. 先删旧唯一索引(引用旧列名)
    op.drop_index("uq_product_attrs_product_key_val", table_name="product_attrs")
    op.drop_index("uq_product_attrs_sku_key_val", table_name="product_attrs")

    # 2. rename 列
    op.alter_column("product_attrs", "attr_key", new_column_name="attr_key_en")
    op.alter_column("product_attrs", "attr_value", new_column_name="attr_value_en")

    # 3. 加 sw 列
    op.add_column("product_attrs", sa.Column(
        "attr_key_sw", sa.String(50), nullable=True,
    ))
    op.add_column("product_attrs", sa.Column(
        "attr_value_sw", sa.String(500), nullable=True,
    ))

    # 4. 加 I18nMixin 列
    op.add_column("product_attrs", sa.Column(
        "source_lang", sa.String(10), nullable=False, server_default="en",
    ))
    op.add_column("product_attrs", sa.Column(
        "trans_meta", sa.JSON(), nullable=False, server_default="{}",
    ))
    op.add_column("product_attrs", sa.Column(
        "i18n_pending_at", sa.DateTime(), nullable=True,
    ))
    op.create_index("ix_product_attrs_i18n_pending_at", "product_attrs", ["i18n_pending_at"])

    # 5. 重建唯一索引(新列名)
    op.execute("""
        CREATE UNIQUE INDEX uq_product_attrs_product_key_val
        ON product_attrs (product_id, attr_key_en, attr_value_en)
        WHERE sku_id IS NULL
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_product_attrs_sku_key_val
        ON product_attrs (sku_id, attr_key_en, attr_value_en)
        WHERE sku_id IS NOT NULL
    """)

    # 6. 数据补丁:初始化 trans_meta
    # 阿里导入的数据:attr_key_en 是英文源,attr_key_zh 可能有中文
    op.execute("""
        UPDATE product_attrs SET
            source_lang = 'en',
            trans_meta = jsonb_build_object(
                'attr_key_en', 'src',
                'attr_key_zh', CASE WHEN attr_key_zh IS NOT NULL AND attr_key_zh != '' THEN 'manual' ELSE 'pending' END,
                'attr_key_sw', 'pending',
                'attr_value_en', 'src',
                'attr_value_zh', CASE WHEN attr_value_zh IS NOT NULL AND attr_value_zh != '' THEN 'manual' ELSE 'pending' END,
                'attr_value_sw', 'pending'
            ),
            i18n_pending_at = NOW()
    """)


def downgrade() -> None:
    # ===================== ProductAttr: 回滚 =====================
    op.drop_index("uq_product_attrs_sku_key_val", table_name="product_attrs")
    op.drop_index("uq_product_attrs_product_key_val", table_name="product_attrs")
    op.drop_index("ix_product_attrs_i18n_pending_at", table_name="product_attrs")

    op.drop_column("product_attrs", "i18n_pending_at")
    op.drop_column("product_attrs", "trans_meta")
    op.drop_column("product_attrs", "source_lang")
    op.drop_column("product_attrs", "attr_value_sw")
    op.drop_column("product_attrs", "attr_key_sw")

    op.alter_column("product_attrs", "attr_key_en", new_column_name="attr_key")
    op.alter_column("product_attrs", "attr_value_en", new_column_name="attr_value")

    # 重建旧唯一索引
    op.execute("""
        CREATE UNIQUE INDEX uq_product_attrs_product_key_val
        ON product_attrs (product_id, attr_key, attr_value)
        WHERE sku_id IS NULL
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_product_attrs_sku_key_val
        ON product_attrs (sku_id, attr_key, attr_value)
        WHERE sku_id IS NOT NULL
    """)

    # ===================== Category: 回滚 =====================
    op.drop_index("ix_categories_i18n_pending_at", table_name="categories")
    op.drop_column("categories", "i18n_pending_at")
    op.drop_column("categories", "trans_meta")
    op.drop_column("categories", "source_lang")
