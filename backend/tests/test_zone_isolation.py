"""央企/客户专区(zone)权限与隔离测试。

后续任务(专区 CRUD / 数据隔离)会陆续往本文件追加用例;
本文件当前覆盖 Task 4:ZONE_MANAGE 权限点同步 + 授予 OPERATOR、Task 9:zone_product v2 字段索引、
Task 5:public_visible() 谓词读侧负向全覆盖(ZONE_ONLY 商品不得出现在任何公开面)。
"""
from __future__ import annotations

import io

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.db.models.permission import Permission
from app.db.models.product import Product, ProductStatus, ProductVisibility
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


# ── Task 5: public_visible() 读侧负向全覆盖 ────────────────────

async def _login_operator(client: AsyncClient) -> dict[str, str]:
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "operator@platform.local", "password": "Aa123456789"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _find_leaf_category_under_l1(db_session, l1_name_zh: str) -> str:
    """按 L1 中文名找一个叶子后代品类 code，用于挂靠首页楼层采样桶。"""
    from app.db.models.category import Category

    l1 = (
        await db_session.execute(
            select(Category).where(Category.level == 1, Category.name_zh == l1_name_zh)
        )
    ).scalar_one()
    leaf = (
        await db_session.execute(
            select(Category).where(
                Category.is_leaf.is_(True),
                Category.is_active.is_(True),
                Category.code.like(f"{l1.code}.%"),
                Category.code.not_like(f"{l1.code}.017.%"),
                Category.code.not_like(f"{l1.code}.020.%"),
            ).order_by(Category.code).limit(1)
        )
    ).scalar_one_or_none()
    assert leaf is not None, f"未找到 L1={l1_name_zh} 下的叶子品类，seed 数据可能变化"
    return leaf.code


async def _make_zone_only_product(
    client: AsyncClient,
    headers: dict,
    db_session,
    *,
    category_code: str,
    spu_code: str,
    brand: str,
    certifications: list[str],
) -> int:
    """造一个 ACTIVE 但 visibility=ZONE_ONLY 的商品(带品牌/认证/主图)，挂在指定叶子品类下。"""
    r = await client.post(
        "/api/v1/operator/products",
        headers=headers,
        json={
            "category_code": category_code,
            "spu_code": spu_code,
            "name": "央企专供测试商品",
            "origin": "中国",
            "brand": brand,
            "certifications": certifications,
            "is_featured": False,
            "status": "DRAFT",
            "source_lang": "zh",
        },
    )
    assert r.status_code == 200, r.text
    pid = r.json()["data"]["id"]

    from PIL import Image as PILImage
    buf = io.BytesIO()
    PILImage.new("RGB", (300, 300), color=(10, 20, 30)).save(buf, format="PNG")
    buf.seek(0)
    r = await client.post(
        f"/api/v1/operator/products/{pid}/images",
        headers=headers,
        files={"file": ("zone.png", buf, "image/png")},
    )
    assert r.status_code == 200, r.text

    r = await client.patch(
        f"/api/v1/operator/products/{pid}/status",
        headers=headers, json={"status": "ACTIVE"},
    )
    assert r.status_code == 200, r.text

    # 专区专供:目前无写侧 API(Task 6/7 才落地)，直接落库翻转 visibility。
    await db_session.execute(
        update(Product).where(Product.id == pid).values(visibility=ProductVisibility.ZONE_ONLY)
    )
    await db_session.commit()
    return pid


@pytest.mark.asyncio
async def test_zone_only_product_hidden_from_all_public_surfaces(client: AsyncClient, db_session):
    """ZONE_ONLY 商品必须在全部公开面(列表/详情/品牌/认证/楼层/L1缩略图)不可见。"""
    headers = await _login_operator(client)
    # "手动工具"(code 04)是 floor-tools 楼层的采样根之一,且非 exclude_category_paths
    # (仅排除"园林工具"/"土杂工具"两个子类),挂靠其下的叶子品类可覆盖首页楼层负向断言。
    cat_code = await _find_leaf_category_under_l1(db_session, "手动工具")

    spu_id = await _make_zone_only_product(
        client, headers, db_session,
        category_code=cat_code,
        spu_code="ZONE-ISO-001",
        brand="__ZONEBRAND__",
        certifications=["__ZONECERT__"],
    )

    # 1. 公开列表不含
    r = await client.get("/api/v1/products?keyword=ZONE-ISO-001")
    assert r.status_code == 200
    assert all(item["id"] != spu_id for item in r.json()["data"]["items"])

    # 2. 公开详情 404(不泄露存在性)
    r = await client.get(f"/api/v1/products/{spu_id}")
    assert r.status_code == 404

    # 3. 品牌筛选聚合不含专供品牌
    r = await client.get("/api/v1/products/brands")
    assert r.status_code == 200
    assert "__ZONEBRAND__" not in r.json()["data"]

    # 4. 认证筛选聚合不含专供认证
    r = await client.get("/api/v1/products/certification-options")
    assert r.status_code == 200
    assert "__ZONECERT__" not in r.json()["data"]

    # 5. 首页楼层不含该 SPU
    r = await client.get("/api/v1/products/home-floors")
    assert r.status_code == 200
    floors = r.json()["data"]["floors"]
    for floor in floors.values():
        assert all(p["id"] != spu_id for p in floor["products"])

    # 6. L1 品类缩略图不指向该商品的主图
    from sqlalchemy import select as _select
    from app.db.models.product_image import ProductImage
    img_row = (
        await db_session.execute(
            _select(ProductImage.image_key).where(ProductImage.product_id == spu_id)
        )
    ).scalar_one()
    r = await client.get("/api/v1/categories/thumbnails")
    assert r.status_code == 200
    thumbnails = r.json()["data"]
    assert all(
        (item["thumbnail"] or "").find(img_row) == -1
        for item in thumbnails
    )


@pytest.mark.asyncio
async def test_get_recent_views_filters_zone_only_products(db_session):
    """get_recent_views() 应过滤 ZONE_ONLY 商品，防止可见性泄露。"""
    from sqlalchemy import select as _select
    from app.db.models.product import Product, ProductStatus, ProductVisibility
    from app.db.models.buyer_event import BuyerEvent
    from app.db.models.user import User
    from app.db.models.buyer_organization import BuyerOrganization
    from app.db.models.buyer_member import BuyerMember
    from app.core.security import hash_password
    from app.services.buyer_event import get_recent_views, EventType

    # 准备买方组织和用户
    buyer_org = BuyerOrganization(name="TestOrgRecent")
    db_session.add(buyer_org)
    await db_session.flush()

    buyer_user = User(
        email="buyer-recent@test.local",
        username="buyer_recent_test",
        name="Buyer Test",
        password_hash=hash_password("Aa123456789"),
    )
    db_session.add(buyer_user)
    await db_session.flush()

    # 将用户加入组织
    db_session.add(BuyerMember(user_id=buyer_user.id, buyer_org_id=buyer_org.id, is_owner=True))
    await db_session.flush()

    # 创建两个 PUBLIC + ACTIVE 商品 P1 和 P2
    p1 = Product(
        spu_code="TEST-P1-ZONE-LEAK",
        name_zh="控制商品1",
        category_code="04.001",
        status=ProductStatus.ACTIVE,
        visibility=ProductVisibility.PUBLIC,
        moq=1,
        unit="PCS",
    )
    db_session.add(p1)
    await db_session.flush()

    p2 = Product(
        spu_code="TEST-P2-ZONE-LEAK",
        name_zh="控制商品2",
        category_code="04.001",
        status=ProductStatus.ACTIVE,
        visibility=ProductVisibility.PUBLIC,
        moq=1,
        unit="PCS",
    )
    db_session.add(p2)
    await db_session.flush()

    # 为 P1 和 P2 各记一条 VIEW_PRODUCT 事件
    event_p1 = BuyerEvent(
        buyer_org_id=buyer_org.id,
        user_id=buyer_user.id,
        event_type=EventType.VIEW_PRODUCT,
        resource_type="product",
        resource_id=p1.id,
    )
    db_session.add(event_p1)

    event_p2 = BuyerEvent(
        buyer_org_id=buyer_org.id,
        user_id=buyer_user.id,
        event_type=EventType.VIEW_PRODUCT,
        resource_type="product",
        resource_id=p2.id,
    )
    db_session.add(event_p2)
    await db_session.flush()

    # 将 P1 翻转到 ZONE_ONLY(模拟运营商隐藏商品到专区)
    await db_session.execute(
        update(Product).where(Product.id == p1.id).values(visibility=ProductVisibility.ZONE_ONLY)
    )
    await db_session.commit()

    # 查询最近浏览: 应包含 P2，不应包含 P1
    recent = await get_recent_views(db_session, buyer_user.id, limit=10)
    recent_ids = [item["id"] for item in recent]

    assert p2.id in recent_ids, "PUBLIC 商品应在最近浏览中"
    assert p1.id not in recent_ids, "ZONE_ONLY 商品不应在最近浏览中（可见性泄露）"


# ── Task 6: resolve_purchase_target() 授权路径集成测试 ────────────────────
# 纯 SKU 解析分支(零/单/多 SKU、variants 消歧、sku_id 一致性)已在
# tests/test_purchase_target_unit.py 覆盖；这里只测跨边界的授权接线
# (grant / 白名单 / zone.status)，因为这些 bug 藏在 DB 缝隙里，mock 掉就失去意义。

from app.db.models.buyer_organization import BuyerOrganization
from app.db.models.zone import Zone, ZoneCategory, ZoneGrant, ZoneProduct
from app.services.purchase_target import ZoneAccessDeniedError, resolve_purchase_target


async def _make_public_product(db_session, *, spu_code: str, status: str = ProductStatus.ACTIVE) -> Product:
    p = Product(
        spu_code=spu_code,
        name_zh="授权测试商品",
        category_code="04.001",
        status=status,
        visibility=ProductVisibility.PUBLIC,
        moq=1,
        unit="PCS",
    )
    db_session.add(p)
    await db_session.flush()
    return p


async def _make_zone_only_product_row(db_session, *, spu_code: str) -> Product:
    p = Product(
        spu_code=spu_code,
        name_zh="专供测试商品",
        category_code="04.001",
        status=ProductStatus.ACTIVE,
        visibility=ProductVisibility.ZONE_ONLY,
        moq=1,
        unit="PCS",
    )
    db_session.add(p)
    await db_session.flush()
    return p


async def _make_zone_with_product(db_session, *, zone_code: str, zone_status: str, product_id: int) -> Zone:
    zone = Zone(code=zone_code, name_zh="测试专区", status=zone_status)
    db_session.add(zone)
    await db_session.flush()

    zc = ZoneCategory(zone_id=zone.id, code="01", name_zh="测试类目")
    db_session.add(zc)
    await db_session.flush()

    db_session.add(ZoneProduct(zone_id=zone.id, spu_id=product_id, zone_category_id=zc.id))
    await db_session.flush()
    return zone


@pytest.mark.asyncio
async def test_resolve_purchase_target_public_active_authorized_without_org(db_session):
    """PUBLIC + ACTIVE 商品：无需 buyer_org_id 即可授权通过。"""
    product = await _make_public_product(db_session, spu_code="RPT-PUBLIC-OK")
    target = await resolve_purchase_target(
        db_session, product_id=product.id, buyer_org_id=None,
    )
    assert target.product.id == product.id
    assert target.sku_id is None


@pytest.mark.asyncio
async def test_resolve_purchase_target_denies_inactive_product_regardless_of_visibility(db_session):
    """非 ACTIVE 商品一律拒绝，不管 visibility 是什么(§6.3:商品自身须可交易)。"""
    product = await _make_public_product(
        db_session, spu_code="RPT-INACTIVE", status=ProductStatus.INACTIVE,
    )
    with pytest.raises(ZoneAccessDeniedError):
        await resolve_purchase_target(db_session, product_id=product.id, buyer_org_id=None)


@pytest.mark.asyncio
async def test_resolve_purchase_target_denies_deleted_product(db_session):
    """软删商品一律拒绝。"""
    product = await _make_public_product(db_session, spu_code="RPT-DELETED")
    from sqlalchemy import func, update
    await db_session.execute(
        update(Product).where(Product.id == product.id).values(deleted_at=func.now())
    )
    await db_session.flush()
    with pytest.raises(ZoneAccessDeniedError):
        await resolve_purchase_target(db_session, product_id=product.id, buyer_org_id=None)


@pytest.mark.asyncio
async def test_resolve_purchase_target_zone_only_denied_without_org(db_session):
    """ZONE_ONLY 商品：buyer_org_id 缺失直接拒绝，不查库。"""
    product = await _make_zone_only_product_row(db_session, spu_code="RPT-ZONE-NOORG")
    with pytest.raises(ZoneAccessDeniedError):
        await resolve_purchase_target(db_session, product_id=product.id, buyer_org_id=None)


@pytest.mark.asyncio
async def test_resolve_purchase_target_zone_only_denied_without_grant(db_session):
    """ZONE_ONLY 商品：org 存在但没有该专区的 ZoneGrant，拒绝。"""
    product = await _make_zone_only_product_row(db_session, spu_code="RPT-ZONE-NOGRANT")
    await _make_zone_with_product(
        db_session, zone_code="ZONE-NOGRANT", zone_status="ACTIVE", product_id=product.id,
    )
    org = BuyerOrganization(name="无授权买方组织")
    db_session.add(org)
    await db_session.flush()

    with pytest.raises(ZoneAccessDeniedError):
        await resolve_purchase_target(db_session, product_id=product.id, buyer_org_id=org.id)


@pytest.mark.asyncio
async def test_resolve_purchase_target_zone_only_denied_when_zone_inactive(db_session):
    """ZONE_ONLY 商品：即使有 grant + 白名单，专区本身 INACTIVE 时也拒绝交易。"""
    product = await _make_zone_only_product_row(db_session, spu_code="RPT-ZONE-INACTIVE")
    zone = await _make_zone_with_product(
        db_session, zone_code="ZONE-INACTIVE", zone_status="INACTIVE", product_id=product.id,
    )
    org = BuyerOrganization(name="停用专区买方组织")
    db_session.add(org)
    await db_session.flush()
    db_session.add(ZoneGrant(zone_id=zone.id, buyer_org_id=org.id))
    await db_session.flush()

    with pytest.raises(ZoneAccessDeniedError):
        await resolve_purchase_target(db_session, product_id=product.id, buyer_org_id=org.id)


@pytest.mark.asyncio
async def test_resolve_purchase_target_zone_only_allowed_with_active_grant(db_session):
    """ZONE_ONLY 商品：grant + 白名单 + 专区 ACTIVE 全满足时授权通过。"""
    product = await _make_zone_only_product_row(db_session, spu_code="RPT-ZONE-OK")
    zone = await _make_zone_with_product(
        db_session, zone_code="ZONE-OK", zone_status="ACTIVE", product_id=product.id,
    )
    org = BuyerOrganization(name="已授权买方组织")
    db_session.add(org)
    await db_session.flush()
    db_session.add(ZoneGrant(zone_id=zone.id, buyer_org_id=org.id))
    await db_session.flush()

    target = await resolve_purchase_target(db_session, product_id=product.id, buyer_org_id=org.id)
    assert target.product.id == product.id


@pytest.mark.asyncio
async def test_resolve_purchase_target_zone_only_denied_for_product_outside_whitelist(db_session):
    """ZONE_ONLY 商品：org 有该专区 grant，但商品不在该专区白名单(zone_products)内，拒绝。"""
    product = await _make_zone_only_product_row(db_session, spu_code="RPT-ZONE-NOTLISTED")
    zone = Zone(code="ZONE-NOTLISTED", name_zh="测试专区2", status="ACTIVE")
    db_session.add(zone)
    await db_session.flush()
    org = BuyerOrganization(name="白名单外买方组织")
    db_session.add(org)
    await db_session.flush()
    db_session.add(ZoneGrant(zone_id=zone.id, buyer_org_id=org.id))
    await db_session.flush()
    # 注意：没有为该 product 建 ZoneProduct 白名单行

    with pytest.raises(ZoneAccessDeniedError):
        await resolve_purchase_target(db_session, product_id=product.id, buyer_org_id=org.id)


@pytest.mark.asyncio
async def test_resolve_purchase_target_resolves_multi_sku_via_db(db_session):
    """端到端：多 ACTIVE SKU 商品经真实 DB 查询(批量加载 attrs)靠 selected_variants 唯一解析。"""
    from app.db.models.product_attr import ProductAttr
    from app.db.models.product_sku import ProductSku, SkuStatus

    product = await _make_public_product(db_session, spu_code="RPT-MULTISKU")
    sku_a = ProductSku(product_id=product.id, sku_code="RPT-MULTISKU-A", moq=1, status=SkuStatus.ACTIVE)
    sku_b = ProductSku(product_id=product.id, sku_code="RPT-MULTISKU-B", moq=1, status=SkuStatus.ACTIVE)
    db_session.add_all([sku_a, sku_b])
    await db_session.flush()

    db_session.add_all([
        ProductAttr(
            product_id=product.id, sku_id=sku_a.id,
            attr_key_en="spec", attr_value_en="A", selectable=True,
        ),
        ProductAttr(
            product_id=product.id, sku_id=sku_b.id,
            attr_key_en="spec", attr_value_en="B", selectable=True,
        ),
    ])
    await db_session.flush()

    target = await resolve_purchase_target(
        db_session, product_id=product.id, buyer_org_id=None,
        selected_variants=[{"attr_name": "spec", "value": "B"}],
    )
    assert target.sku_id == sku_b.id
    assert target.variant_snapshot == [{"attr_name": "spec", "value": "B"}]

    from app.services.purchase_target import VariantUnresolvableError
    with pytest.raises(VariantUnresolvableError):
        await resolve_purchase_target(
            db_session, product_id=product.id, buyer_org_id=None, selected_variants=[],
        )
