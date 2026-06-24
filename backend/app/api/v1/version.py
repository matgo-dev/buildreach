"""构建版本信息端点。"""
import os

from fastapi import APIRouter

router = APIRouter(tags=["version"])


@router.get("/version", summary="当前部署版本")
async def get_version():
    return {
        "commit": os.getenv("BUILD_COMMIT", "dev"),
        "build_time": os.getenv("BUILD_TIME", "-"),
    }
