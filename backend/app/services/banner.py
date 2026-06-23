"""轮播 Banner service。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import get_localized
from app.db.models.banner_slide import BannerSlide
from app.schemas.banner import BannerCreate, BannerDetailOut, BannerOut, BannerUpdate


async def list_active(
    db: AsyncSession,
    *,
    position: str = "home_carousel",
) -> list[BannerOut]:
    """公开接口:返回指定位置的启用 banner,按 sort_order 排序。"""
    stmt = (
        select(BannerSlide)
        .where(BannerSlide.is_active.is_(True))
        .where(BannerSlide.position == position)
        .order_by(BannerSlide.sort_order, BannerSlide.id)
    )
    rows = (await db.execute(stmt)).scalars().all()
    results = []
    for r in rows:
        out = BannerOut.model_validate(r)
        out.title = get_localized(r, "title")
        results.append(out)
    return results


async def list_all(
    db: AsyncSession,
    *,
    position: str | None = None,
) -> list[BannerDetailOut]:
    """Operator 管理接口:返回所有 banner(含未启用)。"""
    stmt = select(BannerSlide).order_by(BannerSlide.sort_order, BannerSlide.id)
    if position is not None:
        stmt = stmt.where(BannerSlide.position == position)
    rows = (await db.execute(stmt)).scalars().all()
    return [BannerDetailOut.model_validate(r) for r in rows]


async def create(db: AsyncSession, payload: BannerCreate) -> BannerDetailOut:
    obj = BannerSlide(**payload.model_dump())
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    return BannerDetailOut.model_validate(obj)


async def update(
    db: AsyncSession, banner_id: int, payload: BannerUpdate,
) -> BannerDetailOut | None:
    stmt = select(BannerSlide).where(BannerSlide.id == banner_id)
    obj = (await db.execute(stmt)).scalar_one_or_none()
    if obj is None:
        return None
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    await db.flush()
    await db.refresh(obj)
    return BannerDetailOut.model_validate(obj)


async def delete(db: AsyncSession, banner_id: int) -> bool:
    stmt = select(BannerSlide).where(BannerSlide.id == banner_id)
    obj = (await db.execute(stmt)).scalar_one_or_none()
    if obj is None:
        return False
    await db.delete(obj)
    await db.flush()
    return True
