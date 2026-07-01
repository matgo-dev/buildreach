"""remove soft delete from 5 config tables

Revision ID: 4a153ef93f20
Revises: 71281a63cdf5
Create Date: 2026-06-09 12:08:44.815770
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4a153ef93f20'
down_revision: Union[str, None] = '71281a63cdf5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_soft_delete_columns(table_name: str) -> None:
    op.drop_constraint(f'fk_{table_name}_deleted_by', table_name, type_='foreignkey')
    op.drop_index(f'ix_{table_name}_deleted_at', table_name=table_name)
    op.drop_column(table_name, 'deleted_by')
    op.drop_column(table_name, 'deleted_at')


def _add_soft_delete_columns(table_name: str) -> None:
    op.add_column(table_name, sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.add_column(table_name, sa.Column('deleted_by', sa.Integer(), nullable=True))
    op.create_index(f'ix_{table_name}_deleted_at', table_name, ['deleted_at'], unique=False)
    op.create_foreign_key(f'fk_{table_name}_deleted_by', table_name, 'users', ['deleted_by'], ['id'])


def upgrade() -> None:
    # 1. 先处理 partial unique index（依赖 deleted_at 列，必须在 drop 列之前）
    # permissions: partial unique index → unique on code
    op.drop_index('uq_permissions_code_active', table_name='permissions')
    op.drop_index('ix_permissions_code', table_name='permissions')

    # role_permissions: partial unique index → UniqueConstraint
    op.drop_index('uq_role_permission_active', table_name='role_permissions')

    # sku_price_tiers: partial unique index → UniqueConstraint
    op.drop_index('uq_sku_price_tiers_sku_qty_active', table_name='sku_price_tiers')

    # product_attrs: 更新 partial unique index 的 WHERE 条件
    op.drop_index('uq_product_attrs_product_key', table_name='product_attrs')
    op.drop_index('uq_product_attrs_sku_key', table_name='product_attrs')

    # 2. 移除 5 张表的 soft delete 字段
    for tbl in ['credit_search_history', 'permissions', 'product_attrs', 'role_permissions', 'sku_price_tiers']:
        _drop_soft_delete_columns(tbl)

    # 3. 重建索引/约束（不再含 deleted_at 条件）
    op.create_index('ix_permissions_code', 'permissions', ['code'], unique=True)

    op.create_unique_constraint('uq_role_permission', 'role_permissions', ['role_id', 'permission_id'])

    op.create_unique_constraint('uq_sku_price_tiers_sku_qty', 'sku_price_tiers', ['sku_id', 'min_qty'])

    op.create_index('uq_product_attrs_product_key', 'product_attrs', ['product_id', 'attr_key'],
                    unique=True, postgresql_where='sku_id IS NULL')
    op.create_index('uq_product_attrs_sku_key', 'product_attrs', ['sku_id', 'attr_key'],
                    unique=True, postgresql_where='sku_id IS NOT NULL')


def downgrade() -> None:
    # Drop constraints/indexes created by upgrade before restoring soft delete columns.
    op.drop_index('uq_product_attrs_sku_key', table_name='product_attrs')
    op.drop_index('uq_product_attrs_product_key', table_name='product_attrs')
    op.drop_constraint('uq_sku_price_tiers_sku_qty', 'sku_price_tiers', type_='unique')
    op.drop_constraint('uq_role_permission', 'role_permissions', type_='unique')
    op.drop_index('ix_permissions_code', table_name='permissions')

    # Restore soft delete columns
    for tbl in ['sku_price_tiers', 'role_permissions', 'product_attrs', 'permissions', 'credit_search_history']:
        _add_soft_delete_columns(tbl)

    # Restore partial unique indexes that depend on deleted_at.
    op.create_index('uq_product_attrs_sku_key', 'product_attrs', ['sku_id', 'attr_key'],
                    unique=True, postgresql_where='sku_id IS NOT NULL AND deleted_at IS NULL')
    op.create_index('uq_product_attrs_product_key', 'product_attrs', ['product_id', 'attr_key'],
                    unique=True, postgresql_where='sku_id IS NULL AND deleted_at IS NULL')

    op.create_index('uq_sku_price_tiers_sku_qty_active', 'sku_price_tiers', ['sku_id', 'min_qty'],
                    unique=True, postgresql_where='deleted_at IS NULL')

    op.create_index('uq_role_permission_active', 'role_permissions', ['role_id', 'permission_id'],
                    unique=True, postgresql_where='deleted_at IS NULL')

    op.create_index('ix_permissions_code', 'permissions', ['code'], unique=False)
    op.create_index('uq_permissions_code_active', 'permissions', ['code'],
                    unique=True, postgresql_where='deleted_at IS NULL')
