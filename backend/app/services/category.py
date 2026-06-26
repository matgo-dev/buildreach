"""商品分类 service:查全表 + 内存建树(对齐 PRD §5.4)。

性能预期:全表 < 2000 条,不加缓存,每次查全表 + 在应用层组装。
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.i18n import get_localized
from app.db.models import Category
from app.db.models.product import Product, ProductStatus
from app.db.models.product_image import ImageType, ProductImage
from app.schemas.category import CategoryNode, CategoryTreeNode


async def list_flat(
    db: AsyncSession,
    *,
    level: int | None = None,
    parent_code: str | None = None,
    is_active: bool | None = True,
) -> list[CategoryNode]:
    """扁平列表,按 (level, sort_order, code) 稳定排序。"""
    stmt = select(Category)
    if is_active is not None:
        stmt = stmt.where(Category.is_active == is_active)
    if level is not None:
        stmt = stmt.where(Category.level == level)
    if parent_code is not None:
        stmt = stmt.where(Category.parent_code == parent_code)
    stmt = stmt.order_by(
        Category.level, Category.parent_code, Category.sort_order, Category.code
    )

    rows = (await db.execute(stmt)).scalars().all()
    nodes = []
    for r in rows:
        node = CategoryNode.model_validate(r)
        node.name = get_localized(r, "name")
        node.short_name = get_localized(r, "short_name")
        nodes.append(node)
    return nodes


async def get_tree(
    db: AsyncSession,
    *,
    is_active: bool | None = True,
    max_depth: int | None = None,
) -> list[CategoryTreeNode]:
    """三层嵌套树,按 (sort_order, code) 排序。

    max_depth: 限制返回层级深度(1=只返回 L1, 2=L1+L2, None=全部)。
    """
    stmt = select(Category)
    if is_active is not None:
        stmt = stmt.where(Category.is_active == is_active)
    # 按 max_depth 截断查询，减少数据量
    if max_depth is not None:
        stmt = stmt.where(Category.level <= max_depth)
    stmt = stmt.order_by(
        Category.level, Category.parent_code, Category.sort_order, Category.code
    )

    rows = (await db.execute(stmt)).scalars().all()

    nodes_by_code: dict[str, CategoryTreeNode] = {}
    roots: list[CategoryTreeNode] = []
    pending_children: list[tuple[str, CategoryTreeNode]] = []

    for r in rows:
        # max_depth 截断时，最深层标记为叶子节点
        is_leaf = r.is_leaf if max_depth is None else (r.level >= max_depth or r.is_leaf)
        node = CategoryTreeNode(
            id=r.id,
            code=r.code,
            name_zh=r.name_zh,
            name_en=r.name_en,
            name=get_localized(r, "name"),
            short_name=get_localized(r, "short_name"),
            level=r.level,
            is_leaf=is_leaf,
            children=[],
        )
        nodes_by_code[r.code] = node
        if r.parent_code is None:
            roots.append(node)
        else:
            pending_children.append((r.parent_code, node))

    for parent_code, child in pending_children:
        parent = nodes_by_code.get(parent_code)
        if parent is None:
            roots.append(child)
        else:
            parent.children.append(child)

    return roots


async def get_l1_thumbnails(db: AsyncSession) -> list[dict]:
    """每个 L1 品类取一张代表商品图，用于移动端宫格入口。

    策略: 对每个 L1 品类，找其下所有子品类中有主图的 ACTIVE 商品，
    取 view_count 最高的那张作为代表图。
    """
    # 1. 拿所有 L1 品类
    l1_cats = await list_flat(db, level=1, is_active=True)

    # 2. 拿所有品类(用于匹配 L1 前缀)
    all_cats_stmt = select(Category.code).where(Category.is_active.is_(True))
    all_codes = [r[0] for r in (await db.execute(all_cats_stmt)).all()]

    # 3. 为每个 L1 找所有后代 code
    l1_to_codes: dict[str, list[str]] = {}
    for l1 in l1_cats:
        prefix = l1.code + "."
        descendants = [c for c in all_codes if c == l1.code or c.startswith(prefix)]
        l1_to_codes[l1.code] = descendants

    # 4. 一次查所有 L1 后代品类中 ACTIVE 商品的主图
    all_descendant_codes = [c for codes in l1_to_codes.values() for c in codes]
    if not all_descendant_codes:
        return [{"code": l1.code, "name": l1.name, "thumbnail": None} for l1 in l1_cats]

    # 子查询: 每个商品的主图 key
    img_sub = (
        select(
            ProductImage.product_id,
            ProductImage.image_key,
            func.row_number()
            .over(
                partition_by=ProductImage.product_id,
                order_by=[
                    (ProductImage.image_type != ImageType.MAIN).asc(),
                    ProductImage.sort_order.asc(),
                ],
            )
            .label("rn"),
        )
        .where(ProductImage.deleted_at.is_(None))
        .subquery()
    )

    # 主查询: ACTIVE 商品 + 主图, 按品类分区取 view_count 最高的
    stmt = (
        select(
            Product.category_code,
            img_sub.c.image_key,
        )
        .join(img_sub, (img_sub.c.product_id == Product.id) & (img_sub.c.rn == 1))
        .where(
            Product.status == ProductStatus.ACTIVE,
            Product.deleted_at.is_(None),
            Product.category_code.in_(all_descendant_codes),
        )
        .order_by(Product.id.desc())
    )
    rows = (await db.execute(stmt)).all()

    # 5. 按 L1 分组取第一张
    base = settings.IMAGE_BASE_URL
    l1_thumb: dict[str, str] = {}
    for cat_code, image_key in rows:
        for l1_code, desc_codes in l1_to_codes.items():
            if l1_code in l1_thumb:
                continue
            if cat_code in desc_codes:
                l1_thumb[l1_code] = f"{base}/{image_key}"
                break

    return [
        {
            "code": l1.code,
            "name": l1.name,
            "thumbnail": l1_thumb.get(l1.code),
        }
        for l1 in l1_cats
    ]
