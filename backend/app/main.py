"""FastAPI 入口:中间件、异常处理、lifespan(同步 RBAC + 种子)。"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.audit.context import get_trace_id
from app.audit.middleware import RequestIDMiddleware
from app.core.config import settings
from app.core.exceptions import BusinessError, success
from app.core.logging_config import setup_logging
from app.db.session import AsyncSessionLocal
from app.rbac.sync import sync_rbac
from app.seed import run_all_seeds
from app.services.glossary_cache import GlossaryCache

logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("App starting up...")
    async with AsyncSessionLocal() as db:
        await sync_rbac(db)
        await run_all_seeds(db)
        await GlossaryCache.load(db)
    logger.info("App startup complete.")
    yield
    logger.info("App shutting down.")


app = FastAPI(
    title="央企海外工程供应链平台 · API",
    version="0.1.0",
    description="MVP 第一轮:认证、RBAC、审计底座",
    lifespan=lifespan,
)

# 中间件顺序:CORS 在最外,Trace ID 在内层(响应头由内向外回写,均能加上)
# 注:带 credentials 时 allow_origins 必须是严格白名单,不能是 "*"(浏览器会拒)
if "*" in settings.CORS_ORIGINS:
    raise RuntimeError(
        "CORS_ORIGINS 不能包含 `*`(refresh cookie 需要带凭证,浏览器拒收 `*` 配合 credentials)"
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Trace-Id"],
)
from app.core.locale import LocaleMiddleware

app.add_middleware(RequestIDMiddleware)
app.add_middleware(LocaleMiddleware)


# ----- 异常处理:统一响应格式 -----

@app.exception_handler(BusinessError)
async def biz_exc_handler(request: Request, exc: BusinessError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.biz_code,
            "message": exc.biz_message,
            "message_key": exc.message_key,
            "data": exc.biz_data,
            "trace_id": get_trace_id(),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exc_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder({
            "code": 42200,
            "message": "Validation error",
            "data": {"errors": exc.errors()},
            "trace_id": get_trace_id(),
        }),
    )


@app.exception_handler(StarletteHTTPException)
async def http_exc_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code * 100,
            "message": str(exc.detail) if exc.detail else "Error",
            "data": None,
            "trace_id": get_trace_id(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exc_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={
            "code": 50000,
            "message": "Internal server error",
            "data": None,
            "trace_id": get_trace_id(),
        },
    )


# ----- 健康检查 -----

@app.get("/healthz", tags=["system"])
async def healthz():
    return success({"status": "ok"})


# ----- 静态文件(商品图片) -----

import os
from pathlib import Path
from fastapi.staticfiles import StaticFiles

_uploads_dir = Path(__file__).resolve().parent.parent / "uploads"
_uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads_dir)), name="uploads")

# ----- 业务路由 -----

from app.api.v1.router import api_router  # noqa: E402

app.include_router(api_router)
