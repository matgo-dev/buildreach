"""错误码段规整守卫测试。

验证:
1. 所有 BusinessError 子类的 biz_code 不等于 http_status × 100(漂移守卫)
2. 所有子类 message_key 非空
3. biz_code 首位与 http_status 类别一致(4xx→4、5xx→5)
4. services/product.py 无裸 raise BusinessError(
5. MessageKey 每个键在前端 zh/en 文案中均有条目
6. 裸 HTTPException 兜底响应 body.code == 40000
7. 关键锚点回归
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import (
    BusinessError,
    InvalidCredentialsError,
    NotFoundError,
)
from app.core.message_keys import MessageKey


def _all_biz_error_classes() -> list[type[BusinessError]]:
    """收集 exceptions 模块中所有 BusinessError 直接/间接子类。"""
    import app.core.exceptions as mod

    classes = []
    for _, obj in inspect.getmembers(mod, inspect.isclass):
        if issubclass(obj, BusinessError) and obj is not BusinessError:
            classes.append(obj)
    return classes


def _instantiate(cls: type[BusinessError]) -> BusinessError:
    """按类名构造实例,处理需要参数的子类。"""
    name = cls.__name__
    if name == "MultipleValidationError":
        return cls(errors=[{"code": 40901, "field": "reg", "message": "dup"}])
    if name == "InvalidProductStatusError":
        return cls("INVALID")
    if name == "SpuCodeExistsError":
        return cls()
    if name == "SkuCodeExistsError":
        return cls()
    if name == "PublishValidationFailedError":
        return cls(["error1"])
    if name == "OnlyDraftDeletableError":
        return cls()
    if name == "SupplierAlreadyBoundError":
        return cls()
    if name == "MaxImagesExceededError":
        return cls(8)
    if name == "ImageFormatInvalidError":
        return cls(".jpg, .png")
    if name == "ImageTooLargeError":
        return cls()
    if name == "ImageTooSmallError":
        return cls()
    if name == "ProductRangeInvalidError":
        return cls("price_min", "price_max")
    if name == "PriceTierInvalidError":
        return cls("test")
    if name == "SkuNotInProductError":
        return cls(1, 2)
    if name == "AttrKeyNotInTemplateError":
        return cls("test_key", "01")
    if name == "RequiredAttrMissingError":
        return cls(["key1"])
    if name == "AttrScopeMismatchError":
        return cls("test_key", "SPU")
    if name == "CategoryNotLeafError":
        return cls("01")
    if name == "ProductNotEditableError":
        return cls("ACTIVE")
    if name == "IllegalTransitionError":
        return cls("DRAFT", "ACTIVE")
    if name == "ImageNotOwnedError":
        return cls(1, 1)
    return cls()


# ── 1. 漂移守卫:biz_code 不得等于 http_status × 100 ──


@pytest.mark.parametrize(
    "cls",
    _all_biz_error_classes(),
    ids=lambda c: c.__name__,
)
def test_biz_code_not_equal_status_times_100(cls):
    instance = _instantiate(cls)
    assert instance.biz_code != instance.status_code * 100, (
        f"{cls.__name__}: biz_code {instance.biz_code} == "
        f"status_code {instance.status_code} × 100,违反分段规则"
    )


# ── 2. message_key 非空 ──


@pytest.mark.parametrize(
    "cls",
    _all_biz_error_classes(),
    ids=lambda c: c.__name__,
)
def test_message_key_not_empty(cls):
    instance = _instantiate(cls)
    assert instance.message_key, (
        f"{cls.__name__}: message_key 为空"
    )


# ── 3. biz_code 首位与 http_status 类别一致 ──


@pytest.mark.parametrize(
    "cls",
    _all_biz_error_classes(),
    ids=lambda c: c.__name__,
)
def test_biz_code_category_matches_http_status(cls):
    instance = _instantiate(cls)
    biz_prefix = str(instance.biz_code)[0]
    status_category = str(instance.status_code)[0]
    assert biz_prefix == status_category, (
        f"{cls.__name__}: biz_code {instance.biz_code} 首位 {biz_prefix} "
        f"与 http_status {instance.status_code} 类别 {status_category} 不一致"
    )


# ── 4. product.py 无裸 raise BusinessError( ──


def test_no_raw_business_error_in_product_service():
    """services/product.py 内不得有裸 raise BusinessError(。"""
    product_py = Path(__file__).resolve().parent.parent / "app" / "services" / "product.py"
    source = product_py.read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise) and node.exc is not None:
            exc = node.exc
            # raise BusinessError(...) 或 raise BusinessError
            if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
                assert exc.func.id != "BusinessError", (
                    f"product.py 第 {node.lineno} 行存在裸 raise BusinessError"
                )
            elif isinstance(exc, ast.Name):
                assert exc.id != "BusinessError", (
                    f"product.py 第 {node.lineno} 行存在裸 raise BusinessError"
                )


# ── 5. MessageKey 每个键在前端 zh/en 文案中有条目 ──


def _get_all_message_keys() -> list[str]:
    keys = []
    for attr in dir(MessageKey):
        if attr.startswith("_"):
            continue
        val = getattr(MessageKey, attr)
        if isinstance(val, str) and val.startswith("error."):
            keys.append(val)
    return keys


def _flatten_json(data: dict, prefix: str = "") -> dict[str, str]:
    """将嵌套 JSON 展平为 dot-notation 键。"""
    result = {}
    for k, v in data.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            result.update(_flatten_json(v, full_key))
        else:
            result[full_key] = v
    return result


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_message_keys_covered_in_frontend(lang):
    import json
    messages_file = Path(__file__).resolve().parent.parent.parent / "frontend" / "messages" / f"{lang}.json"
    data = json.loads(messages_file.read_text())
    flat = _flatten_json(data)
    all_keys = _get_all_message_keys()
    missing = [k for k in all_keys if k not in flat]
    assert not missing, (
        f"{lang}.json 缺少以下 message_key 条目: {missing}"
    )


# ── 6. 裸 HTTPException 兜底 → body.code == 40000 ──


@pytest.mark.asyncio
async def test_raw_http_exception_fallback_code():
    """裸 HTTPException(404) 应返回 body.code=40000,status_code=404。"""
    from fastapi import HTTPException
    from app.main import app

    @app.get("/_test/raw-404")
    async def _raise_raw_404():
        raise HTTPException(status_code=404, detail="not here")

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/_test/raw-404")
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == 40000
        assert body["message_key"] is not None
    finally:
        app.routes[:] = [r for r in app.routes if getattr(r, "path", "") != "/_test/raw-404"]


# ── 7. 锚点回归 ──


def test_not_found_error_biz_code():
    assert NotFoundError().biz_code == 40008


def test_invalid_credentials_biz_code():
    assert InvalidCredentialsError().biz_code == 40001


# ── 8. 前端冻结码不变 ──


def test_frozen_codes_unchanged():
    from app.core.exceptions import (
        SupplierAlreadyRegisteredError,
        EmailAlreadyRegisteredError,
        PhoneAlreadyRegisteredError,
    )
    assert SupplierAlreadyRegisteredError().biz_code == 40901
    assert EmailAlreadyRegisteredError().biz_code == 40902
    assert PhoneAlreadyRegisteredError().biz_code == 40903


# ── 9. 商品错误码锚点 ──


def test_product_error_codes():
    from app.core.exceptions import (
        InvalidProductStatusError,
        SpuCodeExistsError,
        SkuCodeExistsError,
        PublishValidationFailedError,
        OnlyDraftDeletableError,
        SupplierAlreadyBoundError,
        MaxImagesExceededError,
        ImageFormatInvalidError,
        ImageTooLargeError,
        ImageTooSmallError,
        PriceTierInvalidError,
        SkuNotInProductError,
    )
    assert InvalidProductStatusError("X").biz_code == 40201
    assert SpuCodeExistsError().biz_code == 40202
    assert SkuCodeExistsError().biz_code == 40203
    assert PublishValidationFailedError(["e"]).biz_code == 40204
    assert OnlyDraftDeletableError().biz_code == 40205
    assert SupplierAlreadyBoundError().biz_code == 40206
    assert MaxImagesExceededError(8).biz_code == 40207
    assert ImageFormatInvalidError(".jpg").biz_code == 40208
    assert ImageTooLargeError().biz_code == 40209
    assert ImageTooSmallError().biz_code == 40210
    assert PriceTierInvalidError("msg").biz_code == 40211
    assert SkuNotInProductError(1, 2).biz_code == 40212

    from app.core.exceptions import (
        AttrKeyNotInTemplateError,
        RequiredAttrMissingError,
        AttrScopeMismatchError,
    )
    assert AttrKeyNotInTemplateError("k", "01").biz_code == 40213
    assert RequiredAttrMissingError(["k"]).biz_code == 40214
    assert AttrScopeMismatchError("k", "SPU").biz_code == 40215

    from app.core.exceptions import CategoryNotLeafError
    assert CategoryNotLeafError("01").biz_code == 40216
