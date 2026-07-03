"""公开商品可见性谓词 — 读侧唯一真相。

所有面向匿名/公开买方的商品派生查询（列表/详情/筛选聚合/首页楼层/品类缩略图等）
必须应用本谓词，确保 `visibility=ZONE_ONLY` 的专区专供商品不会出现在公开面。
"""
from __future__ import annotations

from sqlalchemy import and_
from sqlalchemy.sql.elements import ColumnElement

from app.db.models.product import Product, ProductStatus, ProductVisibility


def public_visible() -> ColumnElement[bool]:
    """公开商品统一可见性谓词：上架 + 未软删 + 公开可见。

    所有面向匿名/公开的商品派生查询必须 `.where(public_visible())`。
    """
    return and_(
        Product.status == ProductStatus.ACTIVE,
        Product.deleted_at.is_(None),
        Product.visibility == ProductVisibility.PUBLIC,
    )


# 供原生 SQL（text()）拼接使用的等价条件，字面量与上面的 ORM 谓词保持一致。
PUBLIC_VISIBLE_SQL = "status = 'ACTIVE' AND deleted_at IS NULL AND visibility = 'PUBLIC'"
