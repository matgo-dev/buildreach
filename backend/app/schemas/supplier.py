"""供应商目录接口 schema(供应商目录列表页 MVP v0.1)。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SupplierListItem(BaseModel):
    """供应商目录列表 item。

    total_score / grade 来自关联 credit_company 的当前 score_snapshot;
    新注册但异步评分未完成 / 无镜像时为 None(前端显示"评分生成中")。
    tier(T1/T2/T3)由前端从 grade 映射,不在此返回。
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    country_code: str
    status: str
    total_score: int | None = None
    grade: str | None = None
