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
from app.core.exceptions import FulfillmentUnavailableError
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
    """持有一个 httpx.AsyncClient(连接池 + TLS 会话复用)。生产由 lifespan 在启动时建一次
    (init_default_client)、关闭时 aclose;transport 参数仅用于测试注入 httpx.MockTransport。"""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=timeout, transport=transport
        )

    async def aclose(self) -> None:
        await self._client.aclose()

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
        if not settings.S2S_SHARED_SECRET:
            raise FulfillmentUnavailable("fulfillment integration not configured")
        token, jti = sign_s2s_token(iss=ISS_MATGO, aud=AUD_FULFILLMENT_PORTAL, sub=f"org:{org_id}")
        try:
            resp = await self._client.get(
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
            data = body.get("data")
            # 两个端点的 data 都是对象;null / 数组 / 标量说明履约侧信封不对,按不可用处理,
            # 不能原样透传让前端在解构处崩
            if not isinstance(data, dict):
                logger.warning("fulfillment data is not an object org=%s jti=%s path=%s", org_id, jti, path)
                raise FulfillmentUnavailable("malformed data")
            logger.info("fulfillment call ok org=%s jti=%s path=%s", org_id, jti, path)
            return PortalResult("OK", data)
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


# 进程级单例:lifespan 启动时按配置建(未配置则保持 None),关闭时 aclose。
# 在事件循环里建,避免懒初始化;测试不跑 lifespan,靠 dependency_overrides 注入。
_default_client: FulfillmentClient | None = None


def init_default_client() -> None:
    global _default_client
    if settings.s2s_configured:
        _default_client = FulfillmentClient(settings.FULFILLMENT_API_BASE_URL)


async def close_default_client() -> None:
    global _default_client
    if _default_client is not None:
        await _default_client.aclose()
        _default_client = None


def get_fulfillment_client() -> FulfillmentClient:
    """FastAPI 依赖。互通未配置(单例为 None)→ 直接 503,不进路由。"""
    if _default_client is None:
        raise FulfillmentUnavailableError()
    return _default_client
