"""履约后台门户接口 HTTP 客户端(matgo → 履约,BFF 唯一出口)。

契约 §5.2:签 `sub=org:<id>` 短时令牌调 `/api/v1/portal/orders*`,透传 `data`;
履约回 42501(组织未绑定客户)→ NOT_BOUND;详情端点回 404+40008(履约通用 NotFound)→ NOT_FOUND;
超时 / 5xx / 其他 4xx / 非法信封 → 一律 503(FulfillmentUnavailableError,直接从这里抛)。
总预算 TIMEOUT_SECONDS 用 asyncio.timeout 兜整个请求(httpx 的 timeout 是按 connect/read 分阶段的,
不是总上限);不重试,重试只会把预算翻倍。
"""
from __future__ import annotations

import asyncio
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

FULFILLMENT_BIZ_NOT_BOUND = 42501   # 履约 425xx 段:前台组织未绑定客户
FULFILLMENT_BIZ_NOT_FOUND = 40008   # 履约通用 NotFoundError(portal.py 单号不存在走它)
TIMEOUT_SECONDS = 5.0               # 单次调用总预算(连接 + 传输)


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
        # 阶段超时与总预算同值;真正的总上限由 _get 里的 asyncio.timeout 保证
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=httpx.Timeout(timeout), transport=transport
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
        """not_found_is_result:只有详情端点的 404+40008 才是"单号不存在"这个业务结果;
        列表端点不可能 404,若出现(如 base_url 配错、反代 JSON 404)按不可用处理。"""
        if not settings.S2S_SHARED_SECRET:
            raise FulfillmentUnavailableError()
        token, jti = sign_s2s_token(iss=ISS_MATGO, aud=AUD_FULFILLMENT_PORTAL, sub=f"org:{org_id}")
        try:
            async with asyncio.timeout(TIMEOUT_SECONDS):
                resp = await self._client.get(
                    path, params=params, headers={"Authorization": f"Bearer {token}"}
                )
        except (httpx.HTTPError, httpx.InvalidURL, TimeoutError) as exc:
            # InvalidURL 是 ValueError、TimeoutError 来自 asyncio.timeout,都不在 HTTPError 树下
            logger.warning("fulfillment unreachable org=%s jti=%s path=%s: %s", org_id, jti, path, exc)
            raise FulfillmentUnavailableError() from exc

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
                raise FulfillmentUnavailableError()
            logger.info("fulfillment call ok org=%s jti=%s path=%s", org_id, jti, path)
            return PortalResult("OK", data)
        if resp.status_code == 404 and biz_code == FULFILLMENT_BIZ_NOT_BOUND:
            logger.info("fulfillment org not bound org=%s jti=%s", org_id, jti)
            return PortalResult("NOT_BOUND")
        if resp.status_code == 404 and biz_code == FULFILLMENT_BIZ_NOT_FOUND and not_found_is_result:
            return PortalResult("NOT_FOUND")
        logger.warning(
            "fulfillment unexpected response org=%s jti=%s path=%s status=%s code=%s",
            org_id, jti, path, resp.status_code, biz_code,
        )
        raise FulfillmentUnavailableError()


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
