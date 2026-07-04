"""央企专区(common-materials) demo 数据种子:zone + zone_categories + products + demo buyer。

⚠️ 仅供本地/联调环境展示用 —— 是"真实 Excel 选品导入"(Task 11+，暂缓)的占位替身,
手工造的示例数据,不代表真实选品结果。

落库内容:
- 1 个 zone(common-materials,与 /me 已返回的央企专区一致)
- ~5 个 zone_categories(客户视角大类:钢筋类/水泥类/给排水/临时设施/强弱电)
- ~15 个 products,全部 visibility=ZONE_ONLY + status=ACTIVE,category_code 均取自现有平台
  叶子品类(不臆造 code),简单商品(单默认 SKU)与变体商品(2-3 个 ACTIVE SKU,按 spec 区分)混合
- 每个商品对应 1 条 zone_product(挂在其 zone_category 下,source=MANUAL)
- 1 个 demo 买家(BuyerOrganization + User + BuyerMember)+ 对 common-materials 的 zone_grant

商品图片:v1 不种(留空),前端详情页走占位图 fallback。

幂等:按稳定 key 查重,存在则复用/跳过创建,不重复插入 —— 可重复执行。
- zone: code
- zone_category: (zone_id, code)
- product: spu_code(deleted_at IS NULL)
- zone_product: (zone_id, spu_id, zone_category_id)
- buyer_organization: code
- user: email
- buyer_member: (user_id, buyer_org_id)
- zone_grant: (zone_id, buyer_org_id)

用法(仅限本地/联调,需显式 opt-in;生产严禁):
    cd backend
    ALLOW_DEMO_SEED=1 python app/seed_zone_demo.py
可选:DEMO_BUYER_PASSWORD=<自定义强口令> 覆盖默认弱口令。
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# 允许 `python app/seed_zone_demo.py` 直接运行(而不只是 `python -m app.seed_zone_demo`)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models.buyer_member import BuyerMember
from app.db.models.buyer_organization import BuyerOrganization
from app.db.models.category import Category
from app.db.models.product import Product, ProductStatus, ProductVisibility
from app.db.models.product_attr import ProductAttr
from app.db.models.product_sku import ProductSku, SkuStatus
from app.db.models.role import Role, RoleCode
from app.db.models.user import User
from app.db.models.user_role import UserRole
from app.db.models.zone import Zone, ZoneCategory, ZoneGrant, ZoneProduct

ZONE_CODE = "common-materials"
DEMO_BUYER_EMAIL = "zonebuyer@demo.local"
DEMO_BUYER_USERNAME = "zonebuyer"
DEMO_BUYER_PASSWORD = os.environ.get("DEMO_BUYER_PASSWORD", "Aa123456789")
DEMO_BUYER_ORG_CODE = "ZONE-DEMO-BUYER-ORG"

# 客户视角大类(zone_category),code 为专区内自有编号,与平台 category 树无关。
_ZONE_CATEGORIES = [
    {"code": "01", "name_zh": "钢筋类", "name_en": "Rebar"},
    {"code": "02", "name_zh": "水泥类", "name_en": "Cement"},
    {"code": "03", "name_zh": "给排水", "name_en": "Water Supply & Drainage"},
    {"code": "04", "name_zh": "临时设施", "name_en": "Temporary Facilities"},
    {"code": "05", "name_zh": "强弱电", "name_en": "Electrical"},
]

# category_code 均取自现有平台叶子品类(见 data/categories.csv 派生的 categories 表),
# 不臆造 code;语义为示例近似,非真实选品结果。
_PRODUCTS = [
    # 01 钢筋类
    {"zone_category_code": "01", "kind": "simple", "spu_code": "ZONE-DEMO-REBAR-001",
     "name_zh": "钢筋网片", "name_en": "Steel Reinforcing Mesh", "category_code": "09.006.001.004"},
    {"zone_category_code": "01", "kind": "simple", "spu_code": "ZONE-DEMO-REBAR-002",
     "name_zh": "镀锌钢筋网片", "name_en": "Galvanized Steel Wire Mesh", "category_code": "09.006.001.005"},
    {"zone_category_code": "01", "kind": "variant", "spu_code": "ZONE-DEMO-REBAR-003",
     "name_zh": "螺纹钢筋", "name_en": "Deformed Steel Rebar", "category_code": "09.006.001.004",
     "variants": [("Φ12", "Φ12"), ("Φ14", "Φ14"), ("Φ16", "Φ16")]},
    # 02 水泥类
    {"zone_category_code": "02", "kind": "simple", "spu_code": "ZONE-DEMO-CEMENT-001",
     "name_zh": "水泥", "name_en": "Cement", "category_code": "18.002.004.002"},
    {"zone_category_code": "02", "kind": "simple", "spu_code": "ZONE-DEMO-CEMENT-002",
     "name_zh": "建筑用砂", "name_en": "Construction Sand", "category_code": "18.002.004.001"},
    {"zone_category_code": "02", "kind": "variant", "spu_code": "ZONE-DEMO-CEMENT-003",
     "name_zh": "硅酸盐水泥", "name_en": "Portland Cement", "category_code": "18.002.004.003",
     "variants": [("32.5级", "Grade 32.5"), ("42.5级", "Grade 42.5"), ("52.5级", "Grade 52.5")]},
    # 03 给排水
    {"zone_category_code": "03", "kind": "simple", "spu_code": "ZONE-DEMO-WATER-001",
     "name_zh": "PVC排水管", "name_en": "PVC Drainage Pipe", "category_code": "28.003.002.002"},
    {"zone_category_code": "03", "kind": "simple", "spu_code": "ZONE-DEMO-WATER-002",
     "name_zh": "排水管", "name_en": "Drain Pipe", "category_code": "28.003.002.004"},
    {"zone_category_code": "03", "kind": "variant", "spu_code": "ZONE-DEMO-WATER-003",
     "name_zh": "PPR给水管", "name_en": "PPR Water Supply Pipe", "category_code": "28.015.001.001",
     "variants": [("DN20", "DN20"), ("DN25", "DN25"), ("DN32", "DN32")]},
    # 04 临时设施
    {"zone_category_code": "04", "kind": "simple", "spu_code": "ZONE-DEMO-TEMP-001",
     "name_zh": "门式脚手架", "name_en": "Portal Scaffolding", "category_code": "22.004.007.001"},
    {"zone_category_code": "04", "kind": "simple", "spu_code": "ZONE-DEMO-TEMP-002",
     "name_zh": "梯形脚手架", "name_en": "Trapezoidal Scaffolding", "category_code": "22.004.007.002"},
    {"zone_category_code": "04", "kind": "variant", "spu_code": "ZONE-DEMO-TEMP-003",
     "name_zh": "折叠脚手架", "name_en": "Folding Scaffolding", "category_code": "22.004.007.003",
     "variants": [("1.2米", "1.2m"), ("1.5米", "1.5m"), ("1.8米", "1.8m")]},
    # 05 强弱电
    {"zone_category_code": "05", "kind": "simple", "spu_code": "ZONE-DEMO-ELEC-001",
     "name_zh": "工业插座", "name_en": "Industrial Socket", "category_code": "15.002.002.001"},
    {"zone_category_code": "05", "kind": "simple", "spu_code": "ZONE-DEMO-ELEC-002",
     "name_zh": "低烟无卤电线", "name_en": "Low-Smoke Halogen-Free Wire", "category_code": "12.001.014.015"},
    {"zone_category_code": "05", "kind": "variant", "spu_code": "ZONE-DEMO-ELEC-003",
     "name_zh": "BV铜芯电线", "name_en": "BV Copper Core Wire", "category_code": "12.001.014.001",
     "variants": [("2.5mm²", "2.5mm²"), ("4mm²", "4mm²"), ("6mm²", "6mm²")]},
]


async def _get_or_create_zone(db: AsyncSession) -> Zone:
    row = await db.execute(select(Zone).where(Zone.code == ZONE_CODE))
    zone = row.scalar_one_or_none()
    if zone is not None:
        return zone
    zone = Zone(code=ZONE_CODE, name_zh="常用材料", name_en="Common Materials", status="ACTIVE")
    db.add(zone)
    await db.flush()
    return zone


async def _get_or_create_zone_category(
    db: AsyncSession, zone: Zone, *, code: str, name_zh: str, name_en: str, sort_order: int,
) -> ZoneCategory:
    row = await db.execute(
        select(ZoneCategory).where(ZoneCategory.zone_id == zone.id, ZoneCategory.code == code)
    )
    zc = row.scalar_one_or_none()
    if zc is not None:
        return zc
    zc = ZoneCategory(
        zone_id=zone.id, code=code, name_zh=name_zh, name_en=name_en, sort_order=sort_order,
    )
    db.add(zc)
    await db.flush()
    return zc


async def _assert_leaf_category(db: AsyncSession, code: str) -> str:
    """校验 code 是现有平台叶子品类(不臆造品类),返回原 code。"""
    row = await db.execute(
        select(Category).where(
            Category.code == code, Category.is_leaf.is_(True), Category.is_active.is_(True),
        )
    )
    cat = row.scalar_one_or_none()
    if cat is None:
        raise RuntimeError(f"leaf category not found or not leaf/active: {code}")
    return cat.code


async def _get_or_create_simple_product(
    db: AsyncSession, *, spu_code: str, name_zh: str, name_en: str, category_code: str,
    moq: int = 100, unit: str = "PCS",
) -> Product:
    """简单商品:1 个默认 SKU。"""
    row = await db.execute(
        select(Product).where(Product.spu_code == spu_code, Product.deleted_at.is_(None))
    )
    product = row.scalar_one_or_none()
    if product is not None:
        return product

    product = Product(
        spu_code=spu_code, name_zh=name_zh, name_en=name_en, category_code=category_code,
        status=ProductStatus.ACTIVE, visibility=ProductVisibility.ZONE_ONLY,
        moq=moq, unit=unit,
    )
    db.add(product)
    await db.flush()

    sku = ProductSku(
        product_id=product.id, sku_code=f"{spu_code}-DEFAULT",
        name_zh=name_zh, name_en=name_en,
        moq=moq, is_default=True, status=SkuStatus.ACTIVE,
    )
    db.add(sku)
    await db.flush()
    return product


async def _get_or_create_variant_product(
    db: AsyncSession, *, spu_code: str, name_zh: str, name_en: str, category_code: str,
    variants: list[tuple[str, str]], moq: int = 100, unit: str = "PCS",
) -> Product:
    """变体商品:每个 variant 对应 1 个 ACTIVE SKU,以 selectable 属性 spec 区分。"""
    row = await db.execute(
        select(Product).where(Product.spu_code == spu_code, Product.deleted_at.is_(None))
    )
    product = row.scalar_one_or_none()
    if product is not None:
        return product

    product = Product(
        spu_code=spu_code, name_zh=name_zh, name_en=name_en, category_code=category_code,
        status=ProductStatus.ACTIVE, visibility=ProductVisibility.ZONE_ONLY,
        moq=moq, unit=unit,
    )
    db.add(product)
    await db.flush()

    for i, (value_zh, value_en) in enumerate(variants):
        sku = ProductSku(
            product_id=product.id, sku_code=f"{spu_code}-{i + 1}",
            name_zh=f"{name_zh} {value_zh}", name_en=f"{name_en} {value_en}",
            moq=moq, is_default=(i == 0), status=SkuStatus.ACTIVE,
        )
        db.add(sku)
        await db.flush()
        db.add(ProductAttr(
            product_id=product.id, sku_id=sku.id,
            attr_key_zh="规格", attr_key_en="spec",
            attr_value_zh=value_zh, attr_value_en=value_en,
            selectable=True, sort_order=i,
        ))
    await db.flush()
    return product


async def _get_or_create_zone_product(
    db: AsyncSession, zone: Zone, zone_category: ZoneCategory, product: Product, *, sort_order: int,
) -> ZoneProduct:
    row = await db.execute(
        select(ZoneProduct).where(
            ZoneProduct.zone_id == zone.id,
            ZoneProduct.spu_id == product.id,
            ZoneProduct.zone_category_id == zone_category.id,
        )
    )
    zp = row.scalar_one_or_none()
    if zp is not None:
        return zp
    zp = ZoneProduct(
        zone_id=zone.id, spu_id=product.id, zone_category_id=zone_category.id,
        sort_order=sort_order, source="MANUAL",
    )
    db.add(zp)
    await db.flush()
    return zp


async def _get_or_create_demo_buyer(db: AsyncSession) -> tuple[BuyerOrganization, User]:
    row = await db.execute(select(BuyerOrganization).where(BuyerOrganization.code == DEMO_BUYER_ORG_CODE))
    org = row.scalar_one_or_none()
    if org is None:
        org = BuyerOrganization(name="央企专区演示买家组织", code=DEMO_BUYER_ORG_CODE)
        db.add(org)
        await db.flush()

    row = await db.execute(select(User).where(User.email == DEMO_BUYER_EMAIL))
    user = row.scalar_one_or_none()
    if user is None:
        user = User(
            email=DEMO_BUYER_EMAIL, username=DEMO_BUYER_USERNAME, name="央企专区演示买家",
            password_hash=hash_password(DEMO_BUYER_PASSWORD),
        )
        db.add(user)
        await db.flush()
    elif user.username != DEMO_BUYER_USERNAME:
        username_owner = (
            await db.execute(select(User).where(User.username == DEMO_BUYER_USERNAME))
        ).scalar_one_or_none()
        if username_owner is not None and username_owner.id != user.id:
            raise RuntimeError(f"demo buyer username already exists: {DEMO_BUYER_USERNAME}")
        user.username = DEMO_BUYER_USERNAME
        await db.flush()

    # 赋 BUYER 角色:种子直插 User 不走注册流程,否则 me.roles 为空、买家功能(询价篮/RFQ)gating 失效。
    # 幂等——对已存在的账号也会补上缺失的角色。
    buyer_role = (
        await db.execute(select(Role).where(Role.code == RoleCode.BUYER))
    ).scalar_one_or_none()
    if buyer_role is not None:
        has_role = (
            await db.execute(
                select(UserRole).where(
                    UserRole.user_id == user.id, UserRole.role_id == buyer_role.id
                )
            )
        ).scalar_one_or_none()
        if has_role is None:
            db.add(UserRole(user_id=user.id, role_id=buyer_role.id))
            await db.flush()

    row = await db.execute(
        select(BuyerMember).where(BuyerMember.user_id == user.id, BuyerMember.buyer_org_id == org.id)
    )
    member = row.scalar_one_or_none()
    if member is None:
        db.add(BuyerMember(user_id=user.id, buyer_org_id=org.id, is_owner=True))
        await db.flush()

    return org, user


async def _get_or_create_zone_grant(db: AsyncSession, zone: Zone, org: BuyerOrganization) -> ZoneGrant:
    row = await db.execute(
        select(ZoneGrant).where(ZoneGrant.zone_id == zone.id, ZoneGrant.buyer_org_id == org.id)
    )
    grant = row.scalar_one_or_none()
    if grant is not None:
        return grant
    grant = ZoneGrant(zone_id=zone.id, buyer_org_id=org.id)
    db.add(grant)
    await db.flush()
    return grant


async def seed_zone_demo(db: AsyncSession) -> dict:
    """幂等种入央企专区 demo 数据。返回执行汇总,供 CLI 打印。"""
    zone = await _get_or_create_zone(db)

    zone_categories: dict[str, ZoneCategory] = {}
    for i, zc_def in enumerate(_ZONE_CATEGORIES):
        zone_categories[zc_def["code"]] = await _get_or_create_zone_category(
            db, zone, code=zc_def["code"], name_zh=zc_def["name_zh"], name_en=zc_def["name_en"],
            sort_order=i,
        )

    simple_count = 0
    variant_count = 0
    zone_product_count = 0
    sort_counters: dict[str, int] = {}

    for item in _PRODUCTS:
        category_code = await _assert_leaf_category(db, item["category_code"])

        if item["kind"] == "simple":
            product = await _get_or_create_simple_product(
                db, spu_code=item["spu_code"], name_zh=item["name_zh"], name_en=item["name_en"],
                category_code=category_code,
            )
            simple_count += 1
        else:
            product = await _get_or_create_variant_product(
                db, spu_code=item["spu_code"], name_zh=item["name_zh"], name_en=item["name_en"],
                category_code=category_code, variants=item["variants"],
            )
            variant_count += 1

        zc = zone_categories[item["zone_category_code"]]
        sort_counters.setdefault(zc.code, 0)
        await _get_or_create_zone_product(db, zone, zc, product, sort_order=sort_counters[zc.code])
        sort_counters[zc.code] += 1
        zone_product_count += 1

    org, _user = await _get_or_create_demo_buyer(db)
    await _get_or_create_zone_grant(db, zone, org)

    await db.commit()

    return {
        "zone_code": zone.code,
        "demo_login_email": DEMO_BUYER_EMAIL,
        "demo_login_password": DEMO_BUYER_PASSWORD,
        "zone_categories": len(zone_categories),
        "products_simple": simple_count,
        "products_variant": variant_count,
        "products_total": simple_count + variant_count,
        "zone_products": zone_product_count,
    }


async def _execute() -> None:
    """连库执行种子。"""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.core.config import settings

    # 安全护栏:本脚本会创建带已知口令的可登录 demo 买家 + zone 授权,绝不能落到生产。
    # ① 必须显式 opt-in(生产部署链路不会带这个变量);② 硬拦已知生产库主机。
    if os.environ.get("ALLOW_DEMO_SEED") != "1":
        raise SystemExit(
            "拒绝执行:seed_zone_demo 会创建带弱口令的可登录 demo 买家账号 + zone 授权,仅限本地/联调。\n"
            "确认在非生产环境后,设置 ALLOW_DEMO_SEED=1 再重跑;生产环境严禁执行。"
        )
    if "162.19.98.142" in (settings.DATABASE_URL or ""):
        raise SystemExit("拒绝执行:DATABASE_URL 指向生产库(OVH 162.19.98.142),demo 种子严禁落生产。")

    engine = create_async_engine(settings.DATABASE_URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as db:
        summary = await seed_zone_demo(db)
    await engine.dispose()

    print("=" * 60)
    print("央企专区(common-materials) Demo 数据 SUMMARY")
    print("=" * 60)
    print(f"zone_code:            {summary['zone_code']}")
    print(f"demo login email:     {summary['demo_login_email']}")
    print(f"demo login password:  {summary['demo_login_password']}")
    print(f"zone_categories:      {summary['zone_categories']}")
    print(f"products (simple):    {summary['products_simple']}")
    print(f"products (variant):   {summary['products_variant']}")
    print(f"products (total):     {summary['products_total']}")
    print(f"zone_product rows:    {summary['zone_products']}")
    print("注:商品图片本轮未种入(v1 占位),前端详情/列表走占位图 fallback 展示。")


def main() -> None:
    asyncio.run(_execute())


if __name__ == "__main__":
    main()
