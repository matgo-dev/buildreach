"""审计覆盖守卫测试。

设计为"注册表漂移测试":从 FastAPI app 枚举所有写类路由(POST/PUT/PATCH/DELETE),
与下方两个显式集合取并集比对。新增写路由未归类 → 测试失败,迫使作者做一次审计意图决策。

该测试不证明 write_audit 一定被执行(需运行态全量打接口,过重),
只捕获"新增写路由没考虑审计"这一真实失效模式。
"""
from __future__ import annotations

import pytest

from app.main import app


# ── 确实调用 write_audit 的写路由 ──

AUDITED_WRITE_ROUTES: set[tuple[str, str]] = {
    # auth — 登录/注册/登出/改密,全部写审计
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/logout"),
    ("POST", "/api/v1/auth/register/buyer"),
    ("POST", "/api/v1/auth/register/supplier"),
    ("POST", "/api/v1/auth/change-password"),
    # auth — 自助资料变更,均走 me_service 内的 write_audit
    ("PATCH", "/api/v1/auth/me/profile"),
    ("POST", "/api/v1/auth/me/email"),
    ("POST", "/api/v1/auth/me/username"),
    ("POST", "/api/v1/auth/me/phone"),
    # admin — 内部账号管理,均走 user_service / 路由内的 write_audit
    ("POST", "/api/v1/admin/users"),
    ("POST", "/api/v1/admin/users/{user_id}/disable"),
    ("POST", "/api/v1/admin/users/{user_id}/enable"),
    ("POST", "/api/v1/admin/users/{user_id}/force-logout"),
    # credit — AI 评语生成(含 LLM 成本归因审计)
    ("POST", "/api/v1/credit/companies/{company_id}/ai-summary/generate"),
    # operator products — SPU CRUD + 图片 + 上下架
    ("POST", "/api/v1/operator/products"),
    ("PUT", "/api/v1/operator/products/{product_id}"),
    ("PATCH", "/api/v1/operator/products/{product_id}/status"),
    ("DELETE", "/api/v1/operator/products/{product_id}"),
    ("POST", "/api/v1/operator/products/{product_id}/images"),
    ("DELETE", "/api/v1/operator/products/{product_id}/images/{image_id}"),
    ("PATCH", "/api/v1/operator/products/{product_id}/images/{image_id}/set-main"),
    ("PATCH", "/api/v1/operator/products/{product_id}/images/sort"),
    # operator products — SKU CRUD
    ("POST", "/api/v1/operator/products/{product_id}/skus"),
    ("PUT", "/api/v1/operator/products/{product_id}/skus/{sku_id}"),
    ("DELETE", "/api/v1/operator/products/{product_id}/skus/{sku_id}"),
    # operator products — 供货关系(挂 SKU)
    ("POST", "/api/v1/operator/products/{product_id}/skus/{sku_id}/suppliers"),
    ("PUT", "/api/v1/operator/products/{product_id}/skus/{sku_id}/suppliers/{ps_id}"),
    ("DELETE", "/api/v1/operator/products/{product_id}/skus/{sku_id}/suppliers/{ps_id}"),
}


# ── 刻意不审计的写路由(每条带理由)──

AUDIT_EXEMPT_WRITE_ROUTES: set[tuple[str, str]] = {
    # refresh 是静默 token 轮转,频率高、无业务含义,写审计纯噪音
    ("POST", "/api/v1/auth/refresh"),
    # AI 对话创建/消息:交互式阅读行为,非业务决策,逐条审计过重
    ("POST", "/api/v1/credit/ai/conversations"),
    ("POST", "/api/v1/credit/ai/conversations/{conv_id}/messages"),
    # 数据抓取:后台异步任务,请求路径仅入队,不直接产生业务变更
    ("POST", "/api/v1/credit/companies/{company_id}/harvest"),
    # 评分重算:内部计算,结果落 snapshot 表,非用户级审计事件
    ("POST", "/api/v1/credit/companies/{company_id}/recompute"),
    ("POST", "/api/v1/credit/recompute-all"),
    # 搜索历史删除:用户删自己的搜索记录,低风险清理操作
    ("DELETE", "/api/v1/credit/search-history/{history_id}"),
    # 语言偏好切换:个人设置,低风险
    ("PATCH", "/api/v1/auth/me/language"),
}


def _collect_write_routes() -> set[tuple[str, str]]:
    """从 FastAPI app 枚举所有写类路由。"""
    write_methods = {"POST", "PUT", "PATCH", "DELETE"}
    routes: set[tuple[str, str]] = set()
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            for method in route.methods:
                if method in write_methods:
                    routes.add((method, route.path))
    return routes


@pytest.mark.asyncio
async def test_all_write_routes_classified():
    """每个写路由都必须被显式归入 AUDITED 或 EXEMPT,不允许遗漏。"""
    actual = _collect_write_routes()
    classified = AUDITED_WRITE_ROUTES | AUDIT_EXEMPT_WRITE_ROUTES

    unclassified = actual - classified
    assert not unclassified, (
        f"以下写路由未在 test_audit_coverage.py 中归类(AUDITED 或 EXEMPT),\n"
        f"请确认是否需要 write_audit 并添加到对应集合:\n"
        + "\n".join(f"  {m} {p}" for m, p in sorted(unclassified))
    )

    # 反向检查:集合里列的路由确实存在于 app(防止改路径后集合过时)
    stale = classified - actual
    assert not stale, (
        f"以下路由已从 app 中移除,请从 test_audit_coverage.py 的集合中清理:\n"
        + "\n".join(f"  {m} {p}" for m, p in sorted(stale))
    )


@pytest.mark.asyncio
async def test_audited_and_exempt_disjoint():
    """AUDITED 和 EXEMPT 不能有交集。"""
    overlap = AUDITED_WRITE_ROUTES & AUDIT_EXEMPT_WRITE_ROUTES
    assert not overlap, (
        f"以下路由同时出现在 AUDITED 和 EXEMPT 中,请二选一:\n"
        + "\n".join(f"  {m} {p}" for m, p in sorted(overlap))
    )
