"""错误码段规整守卫测试。

验证:
1. 所有 BusinessError 子类的 biz_code 不等于 http_status × 100(漂移守卫)
2. 裸 HTTPException 兜底响应 body.code == 40000
3. 关键锚点回归
"""
from __future__ import annotations

import inspect

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import (
    BusinessError,
    InvalidCredentialsError,
    NotFoundError,
)


def _all_biz_error_classes() -> list[type[BusinessError]]:
    """收集 exceptions 模块中所有 BusinessError 直接/间接子类。"""
    import app.core.exceptions as mod

    classes = []
    for _, obj in inspect.getmembers(mod, inspect.isclass):
        if issubclass(obj, BusinessError) and obj is not BusinessError:
            classes.append(obj)
    return classes


# ── 1. 漂移守卫:biz_code 不得等于 http_status × 100 ──


@pytest.mark.parametrize(
    "cls",
    _all_biz_error_classes(),
    ids=lambda c: c.__name__,
)
def test_biz_code_not_equal_status_times_100(cls):
    """确保没有子类把 HTTP status × 100 当作 biz_code。"""
    # MultipleValidationError 需要传 errors 参数
    if cls.__name__ == "MultipleValidationError":
        instance = cls(errors=[{"code": 40901, "field": "reg", "message": "dup"}])
    else:
        instance = cls()
    assert instance.biz_code != instance.status_code * 100, (
        f"{cls.__name__}: biz_code {instance.biz_code} == "
        f"status_code {instance.status_code} × 100,违反分段规则"
    )


# ── 2. 裸 HTTPException 兜底 → body.code == 40000 ──


@pytest.mark.asyncio
async def test_raw_http_exception_fallback_code():
    """裸 HTTPException(404) 应返回 body.code=40000,status_code=404。"""
    from fastapi import HTTPException
    from app.main import app

    # 注册临时端点触发裸 HTTPException
    @app.get("/_test/raw-404")
    async def _raise_raw_404():
        raise HTTPException(status_code=404, detail="not here")

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/_test/raw-404")
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == 40000, f"期望 40000,实际 {body['code']}"
    finally:
        # 清理临时路由
        app.routes[:] = [r for r in app.routes if getattr(r, "path", "") != "/_test/raw-404"]


# ── 3. 锚点回归 ──


def test_not_found_error_biz_code():
    assert NotFoundError().biz_code == 40008


def test_invalid_credentials_biz_code():
    assert InvalidCredentialsError().biz_code == 40001


# ── 4. 前端冻结码不变 ──


def test_frozen_codes_unchanged():
    """40901/40902/40903 前端冻结码必须保持原值。"""
    from app.core.exceptions import (
        SupplierAlreadyRegisteredError,
        EmailAlreadyRegisteredError,
        PhoneAlreadyRegisteredError,
    )

    assert SupplierAlreadyRegisteredError().biz_code == 40901
    assert EmailAlreadyRegisteredError().biz_code == 40902
    assert PhoneAlreadyRegisteredError().biz_code == 40903
