"""自由询价 + 报价附件 — 增量单测。

覆盖 PRD §4.1 验收用例:
① 自由询价: items-or-remark 校验
② 报价附件: QUOTE scope、关联、响应含 attachments
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.category import Category
from app.db.models.product import Product, ProductStatus


# ── helpers ──────────────────────────────────────────────

_BUYER_EMAIL = "buyer@cscec3b.local"
_BUYER_PWD = "Aa123456789"
_OPERATOR_EMAIL = "operator@platform.local"
_OPERATOR_PWD = "Aa123456789"


async def _login(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    r = await client.post("/api/v1/auth/login", json={"identifier": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


async def _bh(client: AsyncClient) -> dict[str, str]:
    return await _login(client, _BUYER_EMAIL, _BUYER_PWD)


async def _oh(client: AsyncClient) -> dict[str, str]:
    return await _login(client, _OPERATOR_EMAIL, _OPERATOR_PWD)


async def _make_product(db: AsyncSession) -> int:
    """快速在 DB 中创建 ACTIVE 商品,返回 product_id。"""
    cat = (await db.execute(select(Category).where(Category.is_leaf == True, Category.is_active == True).limit(1))).scalar_one()
    p = Product(
        name_zh="FreeRfqTest", name_en="FreeRfqTest",
        category_code=cat.code, spu_code=f"FRT-{int(datetime.now(timezone.utc).timestamp()*1000)}",
        unit="PCS", currency="TZS", status=ProductStatus.ACTIVE,
        source_lang="en", trans_meta={},
    )
    db.add(p)
    await db.flush()
    return p.id


def _make_jpeg() -> bytes:
    """生成合法 JPEG 数据(PIL)。"""
    from PIL import Image
    img = Image.new("RGB", (2, 2), (128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


async def _upload_jpeg(client: AsyncClient, headers: dict) -> int:
    """上传最小 JPEG,返回 attachment id。"""
    jpeg = _make_jpeg()
    r = await client.post(
        "/api/v1/attachments",
        headers=headers,
        files={"file": ("test.jpg", jpeg, "image/jpeg")},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


async def _create_rfq_with_items(client: AsyncClient, headers: dict, product_id: int) -> int:
    """创建一个有行项的 RFQ 并返回 id。"""
    r = await client.post("/api/v1/rfqs", headers=headers, json={
        "items": [{"product_id": product_id, "selected_variants": [], "quantity": "10"}],
        "remark": "test rfq",
    })
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


async def _claim_rfq(client: AsyncClient, op_headers: dict, rfq_id: int):
    """运营受理询价单。"""
    r = await client.patch(f"/api/v1/rfqs/{rfq_id}/claim", headers=op_headers)
    assert r.status_code == 200, r.text


async def _create_other_buyer(db: AsyncSession, client: AsyncClient) -> dict[str, str]:
    """在 DB 中创建不同组织的买方用户,返回其 auth headers。"""
    from app.db.models.user import User
    from app.db.models.buyer_organization import BuyerOrganization
    from app.db.models.buyer_member import BuyerMember
    from app.core.security import hash_password
    from sqlalchemy import select as sa_select

    unique = uuid4().hex[:8]
    email = f"buyer-other-{unique}@test.local"

    # 创建不同的 BuyerOrg
    org = BuyerOrganization(
        name=f"OtherOrg-{unique}",
        address="Test Address",
    )
    db.add(org)
    await db.flush()

    # 创建用户
    user = User(
        email=email,
        password_hash=hash_password("Aa123456789"),
        name=f"OtherBuyer{unique}",
    )
    db.add(user)
    await db.flush()

    # 分配 BUYER 角色
    from app.db.models.role import Role
    from app.db.models.user_role import UserRole
    role = (await db.execute(
        sa_select(Role).where(Role.code == "BUYER")
    )).scalar_one()
    db.add(UserRole(user_id=user.id, role_id=role.id))

    # 加入组织
    db.add(BuyerMember(user_id=user.id, buyer_org_id=org.id, is_owner=True))
    await db.flush()

    # 登录
    return await _login(client, email, "Aa123456789")


# ── ① 自由询价: items-or-remark 校验 ─────────────────────


@pytest.mark.asyncio
async def test_free_rfq_remark_only(client, db_session):
    """① 仅 remark、items 为空 → 成功建单。"""
    bh = await _bh(client)
    r = await client.post("/api/v1/rfqs", headers=bh, json={
        "items": [],
        "remark": "I need 500 bags of cement for Dar es Salaam project",
    })
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "SUBMITTED"
    assert len(data["items"]) == 0
    assert data["remark"] is not None


@pytest.mark.asyncio
async def test_free_rfq_both_empty_rejected(client, db_session):
    """① items 与 remark 皆空 → 422 + code 40529。"""
    bh = await _bh(client)
    r = await client.post("/api/v1/rfqs", headers=bh, json={
        "items": [],
        "remark": "",
    })
    assert r.status_code == 422, r.text
    body = r.json()
    assert body.get("code") == 40529


@pytest.mark.asyncio
async def test_free_rfq_whitespace_remark_rejected(client, db_session):
    """① 纯空白 remark + 无 items → 422（trim 后为空不算非空）。"""
    bh = await _bh(client)
    r = await client.post("/api/v1/rfqs", headers=bh, json={
        "items": [],
        "remark": "   \n  ",
    })
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_free_rfq_no_remark_field(client, db_session):
    """① items 和 remark 都不传（remark 默认 None）→ 422。"""
    bh = await _bh(client)
    r = await client.post("/api/v1/rfqs", headers=bh, json={
        "items": [],
    })
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_free_rfq_items_only_no_remark(client, db_session):
    """① 有 items 但无 remark → 正常建单(只要有其一即可)。"""
    bh = await _bh(client)
    pid = await _make_product(db_session)
    r = await client.post("/api/v1/rfqs", headers=bh, json={
        "items": [{"product_id": pid, "selected_variants": [], "quantity": "10"}],
    })
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_free_rfq_can_be_quoted(client, db_session):
    """① 无 item 的自由询价可正常回填报价(报价行独立于询价行)。"""
    bh = await _bh(client)
    oh = await _oh(client)

    # 创建自由询价单
    r = await client.post("/api/v1/rfqs", headers=bh, json={
        "items": [],
        "remark": "Need bulk construction materials quote",
    })
    assert r.status_code == 200, r.text
    rfq_id = r.json()["data"]["id"]

    # 运营受理
    await _claim_rfq(client, oh, rfq_id)

    # 创建商品用于报价行
    pid = await _make_product(db_session)

    # 回填报价(独立行,不关联 rfq_item)
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=oh, json={
        "header": {"currency": "USD"},
        "lines": [{
            "line_type": "PRODUCT",
            "product_id": pid,
            "product_name": "Cement 42.5",
            "quantity": 500,
            "unit_price": 8.50,
            "uom": "BAG",
        }],
    })
    assert r.status_code == 200, r.text
    quote = r.json()["data"]
    assert len(quote["items"]) == 1
    assert float(quote["total_amount"]) == 4250.0


# ── ② 报价附件 ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_quote_with_attachments(client, db_session):
    """② create_quote 带 attachment_ids → 报价附件关联成功,响应含 attachments。"""
    bh = await _bh(client)
    oh = await _oh(client)
    pid = await _make_product(db_session)
    rfq_id = await _create_rfq_with_items(client, bh, pid)
    await _claim_rfq(client, oh, rfq_id)

    # 运营上传附件
    att_id = await _upload_jpeg(client, oh)

    # 回填报价并关联附件
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=oh, json={
        "header": {"currency": "USD"},
        "lines": [{"product_id": pid, "quantity": 10, "unit_price": 100, "uom": "PCS"}],
        "attachment_ids": [att_id],
    })
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert len(data["attachments"]) == 1
    assert data["attachments"][0]["id"] == att_id


@pytest.mark.asyncio
async def test_quote_without_attachments_empty_list(client, db_session):
    """② 不带附件的报价,响应 attachments 为空列表。"""
    bh = await _bh(client)
    oh = await _oh(client)
    pid = await _make_product(db_session)
    rfq_id = await _create_rfq_with_items(client, bh, pid)
    await _claim_rfq(client, oh, rfq_id)

    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=oh, json={
        "header": {},
        "lines": [{"product_id": pid, "quantity": 10, "unit_price": 50, "uom": "PCS"}],
    })
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["attachments"] == []


@pytest.mark.asyncio
async def test_buyer_can_download_quote_attachment(client, db_session):
    """② 该 RFQ 的买方可下载报价附件。"""
    bh = await _bh(client)
    oh = await _oh(client)
    pid = await _make_product(db_session)
    rfq_id = await _create_rfq_with_items(client, bh, pid)
    await _claim_rfq(client, oh, rfq_id)

    att_id = await _upload_jpeg(client, oh)
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=oh, json={
        "header": {},
        "lines": [{"product_id": pid, "quantity": 10, "unit_price": 50, "uom": "PCS"}],
        "attachment_ids": [att_id],
    })
    assert r.status_code == 200

    # 买方下载
    r = await client.get(f"/api/v1/attachments/{att_id}/download", headers=bh)
    assert r.status_code == 200
    assert "image/jpeg" in r.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_unrelated_buyer_cannot_download_quote_attachment(client, db_session):
    """② 不相关买方无法下载他人 RFQ 的报价附件 → 404。"""
    bh = await _bh(client)
    oh = await _oh(client)
    pid = await _make_product(db_session)
    rfq_id = await _create_rfq_with_items(client, bh, pid)
    await _claim_rfq(client, oh, rfq_id)

    att_id = await _upload_jpeg(client, oh)
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=oh, json={
        "header": {},
        "lines": [{"product_id": pid, "quantity": 10, "unit_price": 50, "uom": "PCS"}],
        "attachment_ids": [att_id],
    })
    assert r.status_code == 200

    # 创建另一个买方(不同组织)
    other_bh = await _create_other_buyer(db_session, client)
    r = await client.get(f"/api/v1/attachments/{att_id}/download", headers=other_bh)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_operator_can_download_quote_attachment(client, db_session):
    """② 任一运营可下载报价附件(不限受理人)。"""
    bh = await _bh(client)
    oh = await _oh(client)
    pid = await _make_product(db_session)
    rfq_id = await _create_rfq_with_items(client, bh, pid)
    await _claim_rfq(client, oh, rfq_id)

    att_id = await _upload_jpeg(client, oh)
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=oh, json={
        "header": {},
        "lines": [{"product_id": pid, "quantity": 10, "unit_price": 50, "uom": "PCS"}],
        "attachment_ids": [att_id],
    })
    assert r.status_code == 200

    # 运营下载
    r = await client.get(f"/api/v1/attachments/{att_id}/download", headers=oh)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_non_uploader_cannot_link_attachment_to_quote(client, db_session):
    """② 运营不能关联他人上传的孤儿附件到报价(uploaded_by 校验)。"""
    bh = await _bh(client)
    oh = await _oh(client)
    pid = await _make_product(db_session)
    rfq_id = await _create_rfq_with_items(client, bh, pid)
    await _claim_rfq(client, oh, rfq_id)

    # 买方上传一个附件(不是运营上传的)
    att_id = await _upload_jpeg(client, bh)

    # 运营尝试关联买方上传的附件到报价 → uploaded_by 不匹配 → 404
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=oh, json={
        "header": {},
        "lines": [{"product_id": pid, "quantity": 10, "unit_price": 50, "uom": "PCS"}],
        "attachment_ids": [att_id],
    })
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_quote_attachments_visible_in_quote_list(client, db_session):
    """② 报价列表接口返回附件信息。"""
    bh = await _bh(client)
    oh = await _oh(client)
    pid = await _make_product(db_session)
    rfq_id = await _create_rfq_with_items(client, bh, pid)
    await _claim_rfq(client, oh, rfq_id)

    att_id = await _upload_jpeg(client, oh)
    r = await client.post(f"/api/v1/rfqs/{rfq_id}/quotes", headers=oh, json={
        "header": {},
        "lines": [{"product_id": pid, "quantity": 10, "unit_price": 50, "uom": "PCS"}],
        "attachment_ids": [att_id],
    })
    assert r.status_code == 200

    # 读取报价列表
    r = await client.get(f"/api/v1/rfqs/{rfq_id}/quotes", headers=oh)
    assert r.status_code == 200, r.text
    quotes = r.json()["data"]
    assert len(quotes) >= 1
    # 最新报价应含附件
    latest = quotes[-1]
    assert len(latest["attachments"]) == 1
    assert latest["attachments"][0]["id"] == att_id