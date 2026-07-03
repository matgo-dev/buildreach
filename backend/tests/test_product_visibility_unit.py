"""public_visible() 谓词纯逻辑单测 — 不连库，只验证编译出的 SQL 条件。"""
from __future__ import annotations

from app.services.product_visibility import public_visible


def test_public_visible_covers_three_conditions():
    sql = str(public_visible().compile(compile_kwargs={"literal_binds": True}))
    assert "status" in sql and "ACTIVE" in sql
    assert "deleted_at IS NULL" in sql
    assert "visibility" in sql and "PUBLIC" in sql
