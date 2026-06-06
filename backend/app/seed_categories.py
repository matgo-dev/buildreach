"""品类种子：九大 L1 品类 + C01 照明的 L2/L3 示例。

数据来源：docs/east-Africa/03_东非平台_商品品类矩阵与SKU建模_v0.1.md
幂等：按 code 查重，已存在则跳过。
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.category import Category, CategoryLevel

logger = logging.getLogger(__name__)

# ── 九大 L1 品类 ──────────────────────────────────────────────
L1_CATEGORIES = [
    ("01", "照明", "Lighting", 10),
    ("02", "电气", "Electrical", 20),
    ("03", "卫浴洁具", "Sanitary & Bath", 30),
    ("04", "五金工具", "Tools & Hardware", 40),
    ("05", "板材", "Boards & Panels", 50),
    ("06", "管件", "Pipes & Fittings", 60),
    ("07", "吊顶装饰", "Ceiling & Decoration", 70),
    ("08", "劳保用品", "Safety & PPE", 80),
    ("09", "结构建材", "Structural & Chemical", 90),
]

# ── C01 照明 L2 ──────────────────────────────────────────────
L2_LIGHTING = [
    ("01.001", "LED 面板灯", "LED Panel Light", 10),
    ("01.002", "LED 灯管", "LED Tube Light", 20),
    ("01.003", "筒灯", "Downlight", 30),
    ("01.004", "投光灯", "Floodlight", 40),
]

# ── C01 照明 L3（挂在 LED 面板灯下） ─────────────────────────
L3_LED_PANEL = [
    ("01.001.001", "嵌入式面板灯", "Recessed LED Panel", 10),
    ("01.001.002", "明装面板灯", "Surface Mounted LED Panel", 20),
    ("01.001.003", "超薄面板灯", "Slim LED Panel", 30),
]

# ── C01 照明 L3（挂在筒灯下） ────────────────────────────────
L3_DOWNLIGHT = [
    ("01.003.001", "固定式筒灯", "Fixed Downlight", 10),
    ("01.003.002", "可调角筒灯", "Adjustable Downlight", 20),
]


async def _upsert_category(
    db: AsyncSession,
    *,
    code: str,
    name_zh: str,
    name_en: str,
    level: int,
    parent_code: str | None = None,
    sort_order: int = 0,
) -> bool:
    row = await db.execute(select(Category).where(Category.code == code))
    if row.scalar_one_or_none() is not None:
        return False
    db.add(Category(
        code=code,
        name_zh=name_zh,
        name_en=name_en,
        level=level,
        parent_code=parent_code,
        sort_order=sort_order,
    ))
    return True


async def seed_categories(db: AsyncSession) -> None:
    """种入九大 L1 品类 + C01 照明 L2/L3 示例数据。"""
    created = 0

    for code, name_zh, name_en, sort_order in L1_CATEGORIES:
        if await _upsert_category(
            db, code=code, name_zh=name_zh, name_en=name_en,
            level=CategoryLevel.L1, sort_order=sort_order,
        ):
            created += 1

    for code, name_zh, name_en, sort_order in L2_LIGHTING:
        if await _upsert_category(
            db, code=code, name_zh=name_zh, name_en=name_en,
            level=CategoryLevel.L2, parent_code="01", sort_order=sort_order,
        ):
            created += 1

    for code, name_zh, name_en, sort_order in L3_LED_PANEL:
        if await _upsert_category(
            db, code=code, name_zh=name_zh, name_en=name_en,
            level=CategoryLevel.L3, parent_code="01.001", sort_order=sort_order,
        ):
            created += 1

    for code, name_zh, name_en, sort_order in L3_DOWNLIGHT:
        if await _upsert_category(
            db, code=code, name_zh=name_zh, name_en=name_en,
            level=CategoryLevel.L3, parent_code="01.003", sort_order=sort_order,
        ):
            created += 1

    await db.commit()

    if created:
        logger.warning("Seed: %d categories created (9 L1 + C01 照明 L2/L3).", created)
    else:
        logger.info("Seed: all categories already exist — skipped.")
