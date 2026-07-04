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


# ── Task 7: cart / rfq 交易入口统一走 resolve_purchase_target ──────────
# 授权路径本身已在上面(Task 6)覆盖；这里只测跨边界接线：
# ZONE_ONLY 越权在 cart/rfq 入口被真实拒绝、sku_id 落库绑定、
# 两条入参路径(variants / sku_id)经解析器回填后指纹一致从而合并成一行。

_DEFAULT_BUYER_EMAIL = "buyer@cscec3b.local"
_DEFAULT_BUYER_PASSWORD = "Aa123456789"


async def _login_default_buyer(client: AsyncClient) -> dict[str, str]:
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": _DEFAULT_BUYER_EMAIL, "password": _DEFAULT_BUYER_PASSWORD},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


async def _default_buyer_org_id(client: AsyncClient, headers: dict) -> int:
    r = await client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["data"]["organization"]["id"]


async def _make_zone_with_category(db_session, *, zone_code: str) -> tuple[Zone, ZoneCategory]:
    zone = Zone(code=zone_code, name_zh="T7测试专区", status="ACTIVE")
    db_session.add(zone)
    await db_session.flush()
    zc = ZoneCategory(zone_id=zone.id, code="01", name_zh="T7测试类目")
    db_session.add(zc)
    await db_session.flush()
    return zone, zc


async def _make_variant_product_in_zone(
    db_session, zone: Zone, zone_category: ZoneCategory, *, spu_code: str,
):
    """ZONE_ONLY + ACTIVE 商品，1 个 selectable 属性(spec)对应 1 个 active SKU。

    只造 1 个 SKU(而非多 SKU)是有意为之：这正是 brief §6.3 收口②要验证的
    "单 SKU 商品，按 variants 加 vs 按 sku_id 加应合并成一行"场景。
    """
    from app.db.models.product_attr import ProductAttr
    from app.db.models.product_sku import ProductSku, SkuStatus

    product = Product(
        spu_code=spu_code, name_zh="专区变体测试商品", category_code="04.001",
        status=ProductStatus.ACTIVE, visibility=ProductVisibility.ZONE_ONLY,
        moq=1, unit="PCS",
    )
    db_session.add(product)
    await db_session.flush()

    sku = ProductSku(product_id=product.id, sku_code=f"{spu_code}-A", moq=1, status=SkuStatus.ACTIVE)
    db_session.add(sku)
    await db_session.flush()

    db_session.add(ProductAttr(
        product_id=product.id, sku_id=sku.id,
        attr_key_en="spec", attr_value_en="A", selectable=True,
    ))
    db_session.add(ZoneProduct(zone_id=zone.id, spu_id=product.id, zone_category_id=zone_category.id))
    await db_session.flush()
    return product, sku


async def _grant_zone_to_default_buyer(client: AsyncClient, db_session, zone: Zone) -> dict:
    """给默认买方(cscec3b)组织授予目标专区 grant，返回其登录头。"""
    headers = await _login_default_buyer(client)
    org_id = await _default_buyer_org_id(client, headers)
    db_session.add(ZoneGrant(zone_id=zone.id, buyer_org_id=org_id))
    await db_session.commit()
    return headers


@pytest.mark.asyncio
async def test_unauthorized_org_cannot_transact_zone_only(client: AsyncClient, db_session):
    """ZONE_ONLY 商品：无 grant 的买方组织加购/询价均被拒绝(不落库)。"""
    product = await _make_zone_only_product_row(db_session, spu_code="T7-DENY-CART-RFQ")
    zone = await _make_zone_with_product(
        db_session, zone_code="ZONE-T7-DENY", zone_status="ACTIVE", product_id=product.id,
    )
    headers = await _login_default_buyer(client)  # 默认买方对该新建专区无 grant

    # 加购拒 — CartProductNotAvailableError(40501, 422)
    r = await client.post(
        "/api/v1/cart/items", headers=headers,
        json={"product_id": product.id, "selected_variants": [], "quantity": 1},
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == 40501

    # 询价拒 — RfqProductNotAvailableError(40506, 422)，商品 id 出现在 offending 列表
    r2 = await client.post(
        "/api/v1/rfqs", headers=headers,
        json={"items": [{"product_id": product.id, "selected_variants": [], "quantity": 1}]},
    )
    assert r2.status_code == 422, r2.text
    assert r2.json()["code"] == 40506
    assert product.id in r2.json()["data"]["offending_product_ids"]

    # 确认真的没有落库
    from app.db.models.cart_item import CartItem
    from app.db.models.rfq_item import RfqItem
    assert (await db_session.execute(
        select(CartItem).where(CartItem.product_id == product.id)
    )).scalar_one_or_none() is None
    assert (await db_session.execute(
        select(RfqItem).where(RfqItem.product_id == product.id)
    )).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_granted_org_can_transact_and_binds_sku(client: AsyncClient, db_session):
    """ZONE_ONLY + 授权买方：加购成功，且落库的 CartItem.sku_id 被正确绑定。"""
    zone, zcat = await _make_zone_with_category(db_session, zone_code="ZONE-T7-GRANT-CART")
    product, sku = await _make_variant_product_in_zone(
        db_session, zone, zcat, spu_code="T7-GRANT-CART",
    )
    headers = await _grant_zone_to_default_buyer(client, db_session, zone)

    r = await client.post(
        "/api/v1/cart/items", headers=headers,
        json={
            "product_id": product.id,
            "selected_variants": [{"attr_name": "spec", "value": "A"}],
            "quantity": 1,
        },
    )
    assert r.status_code == 200, r.text

    from app.db.models.cart_item import CartItem
    item = (await db_session.execute(
        select(CartItem).where(CartItem.product_id == product.id)
    )).scalar_one()
    assert item.sku_id == sku.id


@pytest.mark.asyncio
async def test_granted_org_rfq_binds_sku(client: AsyncClient, db_session):
    """ZONE_ONLY + 授权买方：询价成功，且落库的 RfqItem.sku_id 被正确绑定。"""
    zone, zcat = await _make_zone_with_category(db_session, zone_code="ZONE-T7-GRANT-RFQ")
    product, sku = await _make_variant_product_in_zone(
        db_session, zone, zcat, spu_code="T7-GRANT-RFQ",
    )
    headers = await _grant_zone_to_default_buyer(client, db_session, zone)

    r = await client.post(
        "/api/v1/rfqs", headers=headers,
        json={"items": [{
            "product_id": product.id,
            "selected_variants": [{"attr_name": "spec", "value": "A"}],
            "quantity": 1,
        }]},
    )
    assert r.status_code == 200, r.text

    from app.db.models.rfq_item import RfqItem
    item = (await db_session.execute(
        select(RfqItem).where(RfqItem.product_id == product.id)
    )).scalar_one()
    assert item.sku_id == sku.id


@pytest.mark.asyncio
async def test_add_by_sku_id_and_by_variants_merge_to_one_line(client: AsyncClient, db_session):
    """§6.3 收口②：同一目标两条入参路径(按 variants / 按 sku_id) → 合并成一行,不重复。

    解析器对两条路径回填的 variant_snapshot 均已排序/归一化，
    variant_fingerprint 因此一致 → 既有基于指纹的去重天然生效，无需额外把
    sku_id 加进去重键。
    """
    zone, zcat = await _make_zone_with_category(db_session, zone_code="ZONE-T7-MERGE")
    product, sku = await _make_variant_product_in_zone(
        db_session, zone, zcat, spu_code="T7-MERGE",
    )
    headers = await _grant_zone_to_default_buyer(client, db_session, zone)

    # 路径①：按 variants 加
    r1 = await client.post(
        "/api/v1/cart/items", headers=headers,
        json={
            "product_id": product.id,
            "selected_variants": [{"attr_name": "spec", "value": "A"}],
            "quantity": 1,
        },
    )
    assert r1.status_code == 200, r1.text

    # 路径②：按 sku_id 加(同一目标，不传 selected_variants)
    r2 = await client.post(
        "/api/v1/cart/items", headers=headers,
        json={"product_id": product.id, "sku_id": sku.id, "quantity": 2},
    )
    assert r2.status_code == 200, r2.text

    from app.db.models.cart_item import CartItem
    rows = (await db_session.execute(
        select(CartItem).where(CartItem.product_id == product.id)
    )).scalars().all()
    assert len(rows) == 1, "两条入参路径应合并为一行"
    assert rows[0].quantity == 3
    assert rows[0].sku_id == sku.id


@pytest.mark.asyncio
async def test_unauthorized_org_cannot_update_rfq_with_zone_only(client: AsyncClient, db_session):
    """ZONE_ONLY 商品：无 grant 的买方借草稿改单更新不得绕过授权，PATCH 拒绝且不落库。"""
    # 1. 创建一个 PUBLIC 商品，用于初始化 DRAFT RFQ
    public_product = await _make_public_product(db_session, spu_code="T7-UPDATE-ALLOWED")
    headers = await _login_default_buyer(client)
    org_id = await _default_buyer_org_id(client, headers)

    # 2. 用 PUBLIC 商品创建 DRAFT RFQ
    r_create = await client.post(
        "/api/v1/rfqs", headers=headers,
        json={"items": [{"product_id": public_product.id, "selected_variants": [], "quantity": 1}], "as_draft": True},
    )
    assert r_create.status_code == 200, r_create.text
    rfq_id = r_create.json()["data"]["id"]

    # 3. 创建一个 ZONE_ONLY 商品，对应买方组织无 grant
    zone_only_product = await _make_zone_only_product_row(db_session, spu_code="T7-UPDATE-DENIED")
    zone = await _make_zone_with_product(
        db_session, zone_code="ZONE-T7-UPDATE-DENY", zone_status="ACTIVE", product_id=zone_only_product.id,
    )
    # 注意：不给 org_id 赋予该 zone 的 grant，模拟无权限场景

    # 4. PATCH 草稿 RFQ，试图将 ZONE_ONLY 商品换入
    r_update = await client.patch(
        f"/api/v1/rfqs/{rfq_id}", headers=headers,
        json={"items": [{"product_id": zone_only_product.id, "selected_variants": [], "quantity": 1}]},
    )
    # 预期 422，code 40506 (RfqProductNotAvailableError)，offending_product_ids 包含 zone_only_product.id
    assert r_update.status_code == 422, r_update.text
    assert r_update.json()["code"] == 40506
    assert zone_only_product.id in r_update.json()["data"]["offending_product_ids"]

    # 5. 确认真的没有落库更新：RFQ 仍包含原 PUBLIC 商品，不含 ZONE_ONLY 商品
    from app.db.models.rfq_item import RfqItem
    rfq_items = (await db_session.execute(
        select(RfqItem).where(RfqItem.rfq_id == rfq_id)
    )).scalars().all()
    assert len(rfq_items) == 1, "RFQ 应保持 1 个行项"
    assert rfq_items[0].product_id == public_product.id, "RFQ 应保留原 PUBLIC 商品，未被替换"
    assert not any(item.product_id == zone_only_product.id for item in rfq_items), "ZONE_ONLY 商品不得入库"


# ── Task 8: GET /me 暴露当前买方可见专区列表 ────────────────────

@pytest.mark.asyncio
async def test_me_returns_granted_zone_code(client: AsyncClient, db_session):
    """买方组织持有某专区 grant 时,/me 的 zones 中应含该专区 code。"""
    zone, _zcat = await _make_zone_with_category(db_session, zone_code="ZONE-T8-ME")
    headers = await _grant_zone_to_default_buyer(client, db_session, zone)

    r = await client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200, r.text
    zones = r.json()["data"]["zones"]
    assert any(z["code"] == "ZONE-T8-ME" for z in zones)


@pytest.mark.asyncio
async def test_me_returns_empty_zones_without_grant(client: AsyncClient, db_session):
    """买方组织没有任何专区 grant 时,/me 的 zones 应为空列表。"""
    headers = await _login_default_buyer(client)

    r = await client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["zones"] == []


# ── Task 11: 买方侧专区只读 API(类目导航 + 商品列表 + 商品详情) ────────────────────

@pytest.mark.asyncio
async def test_zone_categories_granted_buyer_sees_categories(client: AsyncClient, db_session):
    """已授权买方:GET /zones/{code}/categories 返回该 zone 的客户视角大类。"""
    zone, zcat = await _make_zone_with_category(db_session, zone_code="ZONE-T11-CATS")
    headers = await _grant_zone_to_default_buyer(client, db_session, zone)

    r = await client.get(f"/api/v1/zones/{zone.code}/categories", headers=headers)
    assert r.status_code == 200, r.text
    items = r.json()["data"]
    assert any(c["id"] == zcat.id and c["code"] == zcat.code for c in items)
    assert items[0]["name_zh"] == zcat.name_zh


@pytest.mark.asyncio
async def test_zone_products_list_and_category_filter(client: AsyncClient, db_session):
    """已授权买方:商品列表返回白名单商品(公开卡片字段),且按 zone_category_code 筛选生效。"""
    zone, zcat = await _make_zone_with_category(db_session, zone_code="ZONE-T11-LIST")
    product, _sku = await _make_variant_product_in_zone(
        db_session, zone, zcat, spu_code="T11-LIST-PROD",
    )
    headers = await _grant_zone_to_default_buyer(client, db_session, zone)

    r = await client.get(f"/api/v1/zones/{zone.code}/products", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["total"] == 1
    item = data["items"][0]
    assert item["id"] == product.id
    assert item["spu_code"] == "T11-LIST-PROD"
    # 公开卡片字段(与 GET /products 一致,前端 mall 组件复用)
    assert "main_image" in item and "moq" in item and "unit" in item

    # 按正确的 zone_category_code 筛选:命中
    r2 = await client.get(
        f"/api/v1/zones/{zone.code}/products",
        headers=headers, params={"zone_category_code": zcat.code},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"]["total"] == 1

    # 按不存在的 zone_category_code 筛选:空结果,不报错
    r3 = await client.get(
        f"/api/v1/zones/{zone.code}/products",
        headers=headers, params={"zone_category_code": "NOPE"},
    )
    assert r3.status_code == 200, r3.text
    assert r3.json()["data"]["total"] == 0
    assert r3.json()["data"]["items"] == []


@pytest.mark.asyncio
async def test_zone_product_detail_includes_variant_skus(client: AsyncClient, db_session):
    """已授权买方:商品详情包含 SKU 变体属性,供前端换购。"""
    zone, zcat = await _make_zone_with_category(db_session, zone_code="ZONE-T11-DETAIL")
    product, sku = await _make_variant_product_in_zone(
        db_session, zone, zcat, spu_code="T11-DETAIL-PROD",
    )
    headers = await _grant_zone_to_default_buyer(client, db_session, zone)

    # 显式 Accept-Language: en —— fixture 只灌了 attr_value_en(source_lang 仍是
    # 默认的 zh),zh locale 下 get_localized 会回退失败拿到空字符串,en 才能直接命中。
    r = await client.get(
        f"/api/v1/zones/{zone.code}/products/{product.id}",
        headers={**headers, "Accept-Language": "en"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["id"] == product.id
    assert data["spu_code"] == "T11-DETAIL-PROD"
    assert len(data["skus"]) == 1
    sku_data = data["skus"][0]
    assert sku_data["id"] == sku.id
    assert any(a["attr_value"] == "A" for a in sku_data["attributes"])


@pytest.mark.asyncio
async def test_zone_access_denied_returns_403_without_grant(client: AsyncClient, db_session):
    """未授权买方:categories/products/detail 三个端点均 403。"""
    zone, zcat = await _make_zone_with_category(db_session, zone_code="ZONE-T11-DENY")
    product, _sku = await _make_variant_product_in_zone(
        db_session, zone, zcat, spu_code="T11-DENY-PROD",
    )
    headers = await _login_default_buyer(client)  # 无 grant

    r1 = await client.get(f"/api/v1/zones/{zone.code}/categories", headers=headers)
    assert r1.status_code == 403, r1.text

    r2 = await client.get(f"/api/v1/zones/{zone.code}/products", headers=headers)
    assert r2.status_code == 403, r2.text

    r3 = await client.get(
        f"/api/v1/zones/{zone.code}/products/{product.id}", headers=headers,
    )
    assert r3.status_code == 403, r3.text


@pytest.mark.asyncio
async def test_zone_access_denied_for_unknown_zone_code(client: AsyncClient, db_session):
    """未知 zone_code:同样 403(不泄露 zone 是否存在)。"""
    headers = await _login_default_buyer(client)
    r = await client.get("/api/v1/zones/NOPE-ZONE/categories", headers=headers)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_zone_product_detail_404_for_product_outside_whitelist(client: AsyncClient, db_session):
    """已授权买方:商品不在该 zone 白名单内(如 PUBLIC 商品)→ 详情 404,不泄露存在性。"""
    zone, _zcat = await _make_zone_with_category(db_session, zone_code="ZONE-T11-404")
    headers = await _grant_zone_to_default_buyer(client, db_session, zone)

    other_product = await _make_public_product(db_session, spu_code="T11-NOT-IN-ZONE")

    r = await client.get(
        f"/api/v1/zones/{zone.code}/products/{other_product.id}", headers=headers,
    )
    assert r.status_code == 404, r.text


# ── 运营端专区授权管理 (operator_zones) 关键路径接线 ────────────────────
# 纯接线(权限门 / 落库 / 幂等 / 撤销),bug 藏在缝隙里,只测关键路径,不追求全覆盖。


@pytest.mark.asyncio
async def test_operator_grant_lifecycle(client: AsyncClient, db_session):
    """运营:列专区 → 授权买家组织(落库)→ 列表可见 → 撤销(删库)。"""
    zone = Zone(code="ZONE-OP-LIFE", name_zh="运营授权测试专区", status="ACTIVE")
    db_session.add(zone)
    org = BuyerOrganization(name="运营授权测试组织")
    db_session.add(org)
    await db_session.commit()

    headers = await _login_operator(client)

    # 专区列表含新建专区
    r = await client.get("/api/v1/operator/zones", headers=headers)
    assert r.status_code == 200, r.text
    assert any(z["code"] == "ZONE-OP-LIFE" for z in r.json()["data"])

    # 授权前列表为空
    r = await client.get(f"/api/v1/operator/zones/{zone.code}/grants", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"] == []

    # 授权 → 落库 + granted_by 记录当前运营
    r = await client.post(
        f"/api/v1/operator/zones/{zone.code}/grants",
        headers=headers, json={"buyer_org_id": org.id},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["buyer_org_id"] == org.id

    row = (await db_session.execute(
        select(ZoneGrant).where(
            ZoneGrant.zone_id == zone.id, ZoneGrant.buyer_org_id == org.id
        )
    )).scalar_one()
    assert row.granted_by is not None

    # 列表可见
    r = await client.get(f"/api/v1/operator/zones/{zone.code}/grants", headers=headers)
    assert any(g["buyer_org_id"] == org.id for g in r.json()["data"])

    # 撤销 → 删库
    r = await client.delete(
        f"/api/v1/operator/zones/{zone.code}/grants/{org.id}", headers=headers
    )
    assert r.status_code == 200, r.text
    assert (await db_session.execute(
        select(ZoneGrant).where(
            ZoneGrant.zone_id == zone.id, ZoneGrant.buyer_org_id == org.id
        )
    )).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_operator_grant_idempotent(client: AsyncClient, db_session):
    """重复授权同一组织不报错,且只落一行。"""
    zone = Zone(code="ZONE-OP-IDEM", name_zh="幂等测试专区", status="ACTIVE")
    db_session.add(zone)
    org = BuyerOrganization(name="幂等测试组织")
    db_session.add(org)
    await db_session.commit()
    headers = await _login_operator(client)

    for _ in range(2):
        r = await client.post(
            f"/api/v1/operator/zones/{zone.code}/grants",
            headers=headers, json={"buyer_org_id": org.id},
        )
        assert r.status_code == 200, r.text

    rows = (await db_session.execute(
        select(ZoneGrant).where(
            ZoneGrant.zone_id == zone.id, ZoneGrant.buyer_org_id == org.id
        )
    )).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_operator_grant_not_found_cases(client: AsyncClient, db_session):
    """未知专区 / 未知组织 → 404。"""
    zone = Zone(code="ZONE-OP-404", name_zh="404测试专区", status="ACTIVE")
    db_session.add(zone)
    await db_session.commit()
    headers = await _login_operator(client)

    # 未知专区
    r = await client.post(
        "/api/v1/operator/zones/NOPE-ZONE/grants",
        headers=headers, json={"buyer_org_id": 1},
    )
    assert r.status_code == 404, r.text

    # 未知组织
    r = await client.post(
        f"/api/v1/operator/zones/{zone.code}/grants",
        headers=headers, json={"buyer_org_id": 999999},
    )
    assert r.status_code == 404, r.text

    # 撤销不存在的授权 → 404
    r = await client.delete(
        f"/api/v1/operator/zones/{zone.code}/grants/999999", headers=headers
    )
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_operator_zone_grants_require_zone_manage(client: AsyncClient, db_session):
    """无 zone:manage 权限的买方访问运营授权接口 → 403。"""
    zone = Zone(code="ZONE-OP-PERM", name_zh="权限门测试专区", status="ACTIVE")
    db_session.add(zone)
    await db_session.commit()
    headers = await _login_default_buyer(client)  # 买方无 zone:manage

    r = await client.get("/api/v1/operator/zones", headers=headers)
    assert r.status_code == 403, r.text

    r = await client.post(
        f"/api/v1/operator/zones/{zone.code}/grants",
        headers=headers, json={"buyer_org_id": 1},
    )
    assert r.status_code == 403, r.text
