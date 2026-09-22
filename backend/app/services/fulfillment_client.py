"""履约后台门户接口 HTTP 客户端(matgo → 履约,BFF 唯一出口)。

契约 §5.2:签 `sub=org:<id>` 短时令牌调 `/api/v1/portal/orders*`,透传 `data`;
履约回 42501(组织未绑定客户)→ NOT_BOUND;单号不存在(404 非 42501)→ NotFound;
超时 / 5xx / 其他 4xx / 非法信封 → 一律视为"不可用",由路由层转 503。
不重试:只读 GET 但对浏览器有 5s 预算,重试只会把超时翻倍。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.core.config import settings
from app.core.s2s_auth import (
    AUD_FULFILLMENT_PORTAL,
    ISS_MATGO,
    sign_s2s_token,
)

logger = logging.getLogger(__name__)

FULFILLMENT_BIZ_NOT_BOUND = 42501
TIMEOUT_SECONDS = 5.0


class FulfillmentUnavailable(Exception):
    """履约不可达 / 响应不可信。message 只进日志,不回浏览器。"""


@dataclass(frozen=True)
class PortalResult:
    kind: Literal["OK", "NOT_BOUND", "NOT_FOUND"]
    data: Any = None


class FulfillmentClient:
    """进程级复用一个 httpx.AsyncClient(连接池 + TLS 会话复用),首次调用时懒建,
    lifespan 关闭时 aclose()。transport 参数仅用于测试注入 httpx.MockTransport;生产留 None。
    base_url 留 None 表示每次从 settings 读(单例用),测试传显式值。"""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: float = TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url_override = base_url
        self._timeout = timeout
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    def _base_url(self) -> str:
        raw = self._base_url_override if self._base_url_override is not None else settings.FULFILLMENT_API_BASE_URL
        return raw.rstrip("/")

    def _get_client(self, base_url: str) -> httpx.AsyncClient:
        # base_url 变化(仅测试 monkeypatch 场景)时重建;生产配置进程内不变
        if self._client is None or str(self._client.base_url).rstrip("/") != base_url:
            self._client = httpx.AsyncClient(
                base_url=base_url, timeout=self._timeout, transport=self._transport
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def list_orders(self, org_id: int, *, page: int, size: int, lang: str) -> PortalResult:
        return await self._get(
            org_id, "/api/v1/portal/orders", {"page": page, "size": size, "lang": lang},
            not_found_is_result=False,
        )

    async def get_order(self, org_id: int, no: str, *, lang: str) -> PortalResult:
        return await self._get(
            org_id, f"/api/v1/portal/orders/{no}", {"lang": lang}, not_found_is_result=True,
        )

    async def _get(
        self, org_id: int, path: str, params: dict[str, Any], *, not_found_is_result: bool
    ) -> PortalResult:
        """not_found_is_result:只有详情端点的 404 才是"单号不存在"这个业务结果;
        列表端点不可能 404,若出现(如 base_url 配错)按不可用处理,不能让用户看到"订单不存在"。"""
        base_url = self._base_url()
        if not base_url or not settings.S2S_SHARED_SECRET:
            raise FulfillmentUnavailable("fulfillment integration not configured")
        token, jti = sign_s2s_token(iss=ISS_MATGO, aud=AUD_FULFILLMENT_PORTAL, sub=f"org:{org_id}")
        try:
            resp = await self._get_client(base_url).get(
                path, params=params, headers={"Authorization": f"Bearer {token}"}
            )
        except (httpx.HTTPError, httpx.InvalidURL) as exc:  # InvalidURL 是 ValueError,不在 HTTPError 树下
            logger.warning("fulfillment unreachable org=%s jti=%s path=%s: %s", org_id, jti, path, exc)
            raise FulfillmentUnavailable(str(exc)) from exc

        try:
            body = resp.json()
        except ValueError:
            body = None
        biz_code = body.get("code") if isinstance(body, dict) else None

        if resp.status_code == 200 and biz_code == 0:
            logger.info("fulfillment call ok org=%s jti=%s path=%s", org_id, jti, path)
            return PortalResult("OK", body.get("data"))
        if resp.status_code == 404 and biz_code == FULFILLMENT_BIZ_NOT_BOUND:
            logger.info("fulfillment org not bound org=%s jti=%s", org_id, jti)
            return PortalResult("NOT_BOUND")
        if resp.status_code == 404 and biz_code is not None and not_found_is_result:
            return PortalResult("NOT_FOUND")
        logger.warning(
            "fulfillment unexpected response org=%s jti=%s path=%s status=%s code=%s",
            org_id, jti, path, resp.status_code, biz_code,
        )
        raise FulfillmentUnavailable(f"status={resp.status_code} code={biz_code}")


# 进程级单例;lifespan shutdown 调 aclose()
default_client = FulfillmentClient()


def get_fulfillment_client() -> FulfillmentClient:
    """FastAPI 依赖;测试用 app.dependency_overrides 注入 MockTransport 客户端。"""
    return default_client
