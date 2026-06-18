"""商品分类 Pydantic schemas(对齐 PRD §5.3)。

- CategoryNode    扁平节点(GET /categories 返回)
- CategoryTreeNode 嵌套节点(GET /categories/tree 返回,children 递归)
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict


class CategoryNode(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name_zh: str
    name_en: str | None = None
    name_sw: str | None = None
    name: str = ""  # 按请求 locale 填充的本地化名称
    level: int
    parent_code: str | None = None
    sort_order: int
    is_leaf: bool = True


class CategoryTreeNode(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name_zh: str
    name_en: str | None = None
    name_sw: str | None = None
    name: str = ""  # 按请求 locale 填充的本地化名称
    level: int
    is_leaf: bool = True
    children: List["CategoryTreeNode"] = []


CategoryTreeNode.model_rebuild()
