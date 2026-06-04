"""商品分类公开 API /api/v1/categories/*(对齐 PRD §5)。

无需登录,不挂权限点。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import success
from app.db.session import get_db
from app.services import category as category_service

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", summary="商品分类扁平列表(可按 level / parent_code 过滤)")
async def list_categories(
    level: int | None = Query(None, ge=1, le=3, description="可选,只返回某一层(1/2/3)"),
    parent_code: str | None = Query(None, description="可选,只返回某父节点(按 code)的子级"),
    is_active: bool = Query(True, description="默认只返回启用的"),
    db: AsyncSession = Depends(get_db),
):
    rows = await category_service.list_flat(
        db, level=level, parent_code=parent_code, is_active=is_active
    )
    return success([r.model_dump() for r in rows])


@router.get("/tree", summary="商品分类三层嵌套树")
async def get_categories_tree(
    is_active: bool = Query(True, description="默认只返回启用的"),
    db: AsyncSession = Depends(get_db),
):
    tree = await category_service.get_tree(db, is_active=is_active)
    return success([n.model_dump() for n in tree])
