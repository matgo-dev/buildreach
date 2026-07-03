"""央企/客户专区(zone)权限与隔离测试。

后续任务(专区 CRUD / 数据隔离)会陆续往本文件追加用例;
本文件当前覆盖 Task 4:ZONE_MANAGE 权限点同步 + 授予 OPERATOR 和 Task 9:zone_product v2 字段索引。
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.models.permission import Permission
from app.db.models.role import Role
from app.db.models.role_permission import RolePermission
from app.rbac.constants import Permissions
from app.rbac.permissions_config import ROLE_PERMISSIONS


@pytest.mark.asyncio
async def test_zone_manage_permission_synced(db_session):
    """启动同步后,zone:manage 权限点应已入库。"""
    row = await db_session.execute(
        select(Permission).where(Permission.code == Permissions.ZONE_MANAGE)
    )
    perm = row.scalar_one_or_none()
    assert perm is not None
    assert perm.name == "管理央企/客户专区"


@pytest.mark.asyncio
async def test_zone_manage_granted_to_operator(db_session):
    """zone:manage 应授予 OPERATOR 角色(且配置与落库一致)。"""
    assert Permissions.ZONE_MANAGE in ROLE_PERMISSIONS["OPERATOR"]

    operator = (
        await db_session.execute(select(Role).where(Role.code == "OPERATOR"))
    ).scalar_one()
    perm = (
        await db_session.execute(
            select(Permission).where(Permission.code == Permissions.ZONE_MANAGE)
        )
    ).scalar_one()

    rp = (
        await db_session.execute(
            select(RolePermission).where(
                RolePermission.role_id == operator.id,
                RolePermission.permission_id == perm.id,
            )
        )
    ).scalar_one_or_none()
    assert rp is not None


@pytest.mark.asyncio
async def test_zone_product_v2_columns_and_indexes(db_session):
    """Task 9: ZoneProduct v2 三字段与两个复合索引应存在。"""
    from sqlalchemy import text

    # Check columns exist
    result = await db_session.execute(
        text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'zone_products'
        AND column_name IN ('source', 'source_batch_id', 'created_by')
        """)
    )
    cols = {row[0] for row in result}
    assert cols == {"source", "source_batch_id", "created_by"}

    # Check indexes exist
    result = await db_session.execute(
        text("""
        SELECT indexname FROM pg_indexes
        WHERE tablename = 'zone_products'
        AND indexname IN ('ix_zone_product_zone_category_sort', 'ix_zone_product_zone_spu')
        """)
    )
    idxs = {row[0] for row in result}
    assert idxs == {"ix_zone_product_zone_category_sort", "ix_zone_product_zone_spu"}
