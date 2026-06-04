"""聚合所有 v1 路由。"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    admin_audit,
    admin_users,
    auth,
    categories,
    credit,
    debug,
    suppliers,
    test_rbac,
)
from app.core.config import settings

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(admin_users.router)
api_router.include_router(admin_audit.router)
api_router.include_router(test_rbac.router)
api_router.include_router(categories.router)
api_router.include_router(credit.router)
api_router.include_router(suppliers.router)

# /api/v1/_debug/* 仅当 ENABLE_DEBUG_API=true 时挂载(默认 true,生产应关)
if settings.ENABLE_DEBUG_API:
    api_router.include_router(debug.router)
