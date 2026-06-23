"""聚合所有 v1 路由。"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    admin_audit,
    admin_users,
    attachments,
    auth,
    banners,
    buyer_events,
    buyer_prefs,
    cart,
    categories,
    contact,
    credit,
    debug,
    operator_analytics,
    operator_banners,
    operator_buyers,
    operator_products,
    products,
    quotes,
    rfqs,
    suppliers,
    test_rbac,
    uploads,
)
from app.core.config import settings

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(attachments.router)
api_router.include_router(auth.router)
api_router.include_router(admin_users.router)
api_router.include_router(admin_audit.router)
api_router.include_router(test_rbac.router)
api_router.include_router(banners.router)
api_router.include_router(categories.router)
api_router.include_router(contact.router)
api_router.include_router(credit.router)
api_router.include_router(products.router)
api_router.include_router(operator_banners.router)
api_router.include_router(operator_buyers.router)
api_router.include_router(operator_products.router)
api_router.include_router(suppliers.router)
api_router.include_router(buyer_events.router)
api_router.include_router(buyer_prefs.router)
api_router.include_router(operator_analytics.router)
api_router.include_router(cart.router)
api_router.include_router(rfqs.router)
api_router.include_router(quotes.router)
api_router.include_router(uploads.router)

# /api/v1/_debug/* 仅当 ENABLE_DEBUG_API=true 时挂载(默认 true,生产应关)
if settings.ENABLE_DEBUG_API:
    api_router.include_router(debug.router)
