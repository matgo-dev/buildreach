"""add soft delete fields to 9 business tables

Revision ID: 71281a63cdf5
Revises: 5c1c21e80674
Create Date: 2026-06-09 10:40:56.807136
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '71281a63cdf5'
down_revision: Union[str, None] = '5c1c21e80674'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_soft_delete_columns(table_name: str) -> None:
    """给一张表加 deleted_at + deleted_by + 索引 + FK。"""
    op.add_column(table_name, sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.add_column(table_name, sa.Column('deleted_by', sa.Integer(), nullable=True))
    op.create_index(
        f'ix_{table_name}_deleted_at', table_name, ['deleted_at'], unique=False,
    )
    op.create_foreign_key(
        f'fk_{table_name}_deleted_by', table_name, 'users', ['deleted_by'], ['id'],
    )


def _drop_soft_delete_columns(table_name: str) -> None:
    """回滚：删除 deleted_at + deleted_by。"""
    op.drop_constraint(f'fk_{table_name}_deleted_by', table_name, type_='foreignkey')
    op.drop_index(f'ix_{table_name}_deleted_at', table_name=table_name)
    op.drop_column(table_name, 'deleted_by')
    op.drop_column(table_name, 'deleted_at')


def upgrade() -> None:
    # 1. 9 张表加 deleted_at + deleted_by
    for tbl in [
        'products', 'product_skus', 'product_images', 'product_attrs',
        'sku_price_tiers', 'product_suppliers', 'permissions',
        'role_permissions', 'credit_search_history',
    ]:
        _add_soft_delete_columns(tbl)

    # 2. 唯一约束 → partial unique index（WHERE deleted_at IS NULL）
    # products.spu_code
    op.drop_constraint('uq_products_spu_code', 'products', type_='unique')
    op.create_index(
        'uq_products_spu_code_active', 'products', ['spu_code'],
        unique=True, postgresql_where='deleted_at IS NULL',
    )

    # product_skus.sku_code
    op.drop_constraint('product_skus_sku_code_key', 'product_skus', type_='unique')
    op.create_index(
        'uq_product_skus_sku_code_active', 'product_skus', ['sku_code'],
        unique=True, postgresql_where='deleted_at IS NULL',
    )

    # product_skus 默认 SKU 索引：加 deleted_at IS NULL 条件
    op.drop_index('ix_product_skus_default', table_name='product_skus')
    op.create_index(
        'ix_product_skus_default', 'product_skus', ['product_id'],
        unique=True, postgresql_where='is_default AND deleted_at IS NULL',
    )

    # product_attrs 唯一索引：加 deleted_at IS NULL 条件
    op.drop_index('uq_product_attrs_product_key', table_name='product_attrs')
    op.create_index(
        'uq_product_attrs_product_key', 'product_attrs', ['product_id', 'attr_key'],
        unique=True, postgresql_where='sku_id IS NULL AND deleted_at IS NULL',
    )
    op.drop_index('uq_product_attrs_sku_key', table_name='product_attrs')
    op.create_index(
        'uq_product_attrs_sku_key', 'product_attrs', ['sku_id', 'attr_key'],
        unique=True, postgresql_where='sku_id IS NOT NULL AND deleted_at IS NULL',
    )

    # sku_price_tiers (sku_id, min_qty)
    op.drop_constraint('uq_sku_price_tiers_sku_qty', 'sku_price_tiers', type_='unique')
    op.create_index(
        'uq_sku_price_tiers_sku_qty_active', 'sku_price_tiers', ['sku_id', 'min_qty'],
        unique=True, postgresql_where='deleted_at IS NULL',
    )

    # product_suppliers (sku_id, supplier_org_id)
    op.drop_constraint('uq_product_suppliers_sku_supplier', 'product_suppliers', type_='unique')
    op.create_index(
        'uq_product_suppliers_sku_supplier_active', 'product_suppliers',
        ['sku_id', 'supplier_org_id'],
        unique=True, postgresql_where='deleted_at IS NULL',
    )

    # permissions.code
    op.drop_constraint('uq_permissions_code', 'permissions', type_='unique')
    op.create_index(
        'uq_permissions_code_active', 'permissions', ['code'],
        unique=True, postgresql_where='deleted_at IS NULL',
    )

    # role_permissions (role_id, permission_id)
    op.drop_constraint('uq_role_permission', 'role_permissions', type_='unique')
    op.create_index(
        'uq_role_permission_active', 'role_permissions', ['role_id', 'permission_id'],
        unique=True, postgresql_where='deleted_at IS NULL',
    )


def downgrade() -> None:
    # 恢复唯一约束
    op.drop_index('uq_role_permission_active', table_name='role_permissions',
                   postgresql_where='deleted_at IS NULL')
    op.create_unique_constraint('uq_role_permission', 'role_permissions',
                                ['role_id', 'permission_id'])

    op.drop_index('uq_permissions_code_active', table_name='permissions',
                   postgresql_where='deleted_at IS NULL')
    op.create_unique_constraint('uq_permissions_code', 'permissions', ['code'])

    op.drop_index('uq_product_suppliers_sku_supplier_active', table_name='product_suppliers',
                   postgresql_where='deleted_at IS NULL')
    op.create_unique_constraint('uq_product_suppliers_sku_supplier', 'product_suppliers',
                                ['sku_id', 'supplier_org_id'])

    op.drop_index('uq_sku_price_tiers_sku_qty_active', table_name='sku_price_tiers',
                   postgresql_where='deleted_at IS NULL')
    op.create_unique_constraint('uq_sku_price_tiers_sku_qty', 'sku_price_tiers',
                                ['sku_id', 'min_qty'])

    op.drop_index('uq_product_attrs_sku_key', table_name='product_attrs')
    op.create_index('uq_product_attrs_sku_key', 'product_attrs', ['sku_id', 'attr_key'],
                    unique=True, postgresql_where='sku_id IS NOT NULL')
    op.drop_index('uq_product_attrs_product_key', table_name='product_attrs')
    op.create_index('uq_product_attrs_product_key', 'product_attrs', ['product_id', 'attr_key'],
                    unique=True, postgresql_where='sku_id IS NULL')

    op.drop_index('ix_product_skus_default', table_name='product_skus')
    op.create_index('ix_product_skus_default', 'product_skus', ['product_id'],
                    unique=True, postgresql_where='is_default')

    op.drop_index('uq_product_skus_sku_code_active', table_name='product_skus',
                   postgresql_where='deleted_at IS NULL')
    op.create_unique_constraint('product_skus_sku_code_key', 'product_skus', ['sku_code'])

    op.drop_index('uq_products_spu_code_active', table_name='products',
                   postgresql_where='deleted_at IS NULL')
    op.create_unique_constraint('uq_products_spu_code', 'products', ['spu_code'])

    # 删除 soft delete 列
    for tbl in [
        'credit_search_history', 'role_permissions', 'permissions',
        'product_suppliers', 'sku_price_tiers', 'product_attrs',
        'product_images', 'product_skus', 'products',
    ]:
        _drop_soft_delete_columns(tbl)
