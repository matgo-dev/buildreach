"""买方浏览偏好路由 /api/v1/buyer/browse-preferences"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, CurrentUser
from app.core.exceptions import success
from app.db.session import get_db
from app.rbac.constants import Permissions
from app.rbac.guards import require_permission
from app.services import auth_service

router = APIRouter(prefix="/buyer", tags=["buyer"])


class BrowsePreferencesOut(BaseModel):
    category_codes: list[str]


class BrowsePreferencesIn(BaseModel):
    category_codes: list[str]


@router.get(
    "/browse-preferences",
    summary="读取浏览偏好",
    dependencies=[Depends(require_permission(Permissions.BUYER_PREF_READ))],
)
async def get_browse_preferences(
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    codes = await auth_service.get_browse_preferences(db, current.id)
    return success(BrowsePreferencesOut(category_codes=codes).model_dump())


@router.put(
    "/browse-preferences",
    summary="全量替换浏览偏好",
    dependencies=[Depends(require_permission(Permissions.BUYER_PREF_WRITE))],
)
async def replace_browse_preferences(
    body: BrowsePreferencesIn,
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    codes = await auth_service.replace_browse_preferences(
        db, current.id, body.category_codes, request=request,
    )
    return success(BrowsePreferencesOut(category_codes=codes).model_dump())
