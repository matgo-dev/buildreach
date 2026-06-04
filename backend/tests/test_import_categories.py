"""Excel 导入脚本测试(对齐 PRD §4 / scripts/import_categories.py)。

脚本本身用 sync SQLAlchemy(psycopg),所以不依赖 conftest 的 async fixture,
独立建 sync engine 跑测试。drop_all + create_all 每个 test 隔离。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.base import Base
from app.db import models as _models  # noqa: F401
from app.db.models import Category
from app.db.url import prepare_sync_url
from scripts.import_categories import (
    ExcelL1,
    ExcelL2,
    ExcelTree,
    import_from_xlsx,
    parse_xlsx,
    validate_xlsx_path,
)


TEST_DSN = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://liujingjing@localhost:5433/overseas_supply_test",
)
SYNC_DSN = prepare_sync_url(TEST_DSN)


# ---------- fixture: sync session ----------


@pytest.fixture
def sync_db():
    engine = create_engine(SYNC_DSN, poolclass=None)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(engine)
    engine.dispose()


# ---------- helpers ----------


def _make_xlsx(tmp_path: Path, rows: list[tuple], name: str = "cat.xlsx") -> Path:
    wb = Workbook()
    ws = wb.active
    ws.append(("一级分类", "二级分类", "三级分类"))
    for row in rows:
        ws.append(row)
    path = tmp_path / name
    wb.save(path)
    return path


def _tree_with(rows: list[tuple[str, str, list[str]]]) -> ExcelTree:
    """直接构造 ExcelTree,绕过 xlsx,用于纯算法测试。"""
    tree = ExcelTree()
    l1_idx: dict[str, ExcelL1] = {}
    l2_idx: dict[tuple[str, str], ExcelL2] = {}
    for l1_name, l2_name, l3_names in rows:
        if l1_name not in l1_idx:
            n1 = ExcelL1(name_zh=l1_name)
            l1_idx[l1_name] = n1
            tree.l1_nodes.append(n1)
        l1 = l1_idx[l1_name]
        key = (l1_name, l2_name)
        if key not in l2_idx:
            n2 = ExcelL2(name_zh=l2_name)
            l2_idx[key] = n2
            l1.l2_nodes.append(n2)
        l2 = l2_idx[key]
        for x in l3_names:
            if x not in l2.l3_names:
                l2.l3_names.append(x)
    return tree


# ---------- parse_xlsx ----------


def test_parse_xlsx_header_match_and_l3_split(tmp_path):
    path = _make_xlsx(tmp_path, [("土建", "钢筋", "螺纹钢、圆钢")])
    tree = parse_xlsx(path)
    assert len(tree.l1_nodes) == 1
    assert tree.l1_nodes[0].name_zh == "土建"
    assert tree.l1_nodes[0].l2_nodes[0].l3_names == ["螺纹钢", "圆钢"]


def test_parse_xlsx_l1_forward_fill(tmp_path):
    """L1 列省略时向下填充。"""
    path = _make_xlsx(
        tmp_path,
        [
            ("土建", "钢筋", "螺纹钢"),
            (None, "商砼", "C30"),
            (None, "型材", "工字钢"),
        ],
    )
    tree = parse_xlsx(path)
    assert len(tree.l1_nodes) == 1
    assert [l2.name_zh for l2 in tree.l1_nodes[0].l2_nodes] == ["钢筋", "商砼", "型材"]


def test_parse_xlsx_l3_all_delimiters(tmp_path):
    """支持 、 , ， ; ； 与换行 共 6 种分隔符。"""
    path = _make_xlsx(tmp_path, [("土建", "钢筋", "A、B,C，D;E；F\nG")])
    tree = parse_xlsx(path)
    assert tree.l1_nodes[0].l2_nodes[0].l3_names == ["A", "B", "C", "D", "E", "F", "G"]


def test_parse_xlsx_l3_dedup_same_parent(tmp_path):
    """同 parent 下同名 L3 去重。"""
    path = _make_xlsx(tmp_path, [("土建", "钢筋", "A、A、B")])
    tree = parse_xlsx(path)
    assert tree.l1_nodes[0].l2_nodes[0].l3_names == ["A", "B"]


def test_parse_xlsx_trailing_empty_segment(tmp_path):
    """末尾空段(分隔符余项)被丢弃。"""
    path = _make_xlsx(tmp_path, [("土建", "钢筋", "A、B、")])
    tree = parse_xlsx(path)
    assert tree.l1_nodes[0].l2_nodes[0].l3_names == ["A", "B"]


def test_parse_xlsx_invalid_header_fails(tmp_path):
    """表头不含 一级/二级/三级 → fail-fast。"""
    path = tmp_path / "bad.xlsx"
    wb = Workbook()
    wb.active.append(("a", "b", "c"))
    wb.save(path)
    with pytest.raises(SystemExit):
        parse_xlsx(path)


def test_parse_xlsx_missing_l2_fails(tmp_path):
    """L2 必须有值。"""
    path = _make_xlsx(tmp_path, [("土建", None, "螺纹钢")])
    with pytest.raises(SystemExit):
        parse_xlsx(path)


# ---------- import_from_xlsx 核心算法 ----------


def test_import_empty_db_all_new(sync_db):
    tree = _tree_with(
        [
            ("土建", "钢筋", ["螺纹钢"]),
            ("土建", "商砼", ["C30"]),
            ("安装", "弱电", ["电缆"]),
        ]
    )
    stats = import_from_xlsx(sync_db, tree)
    sync_db.commit()
    assert stats.inserted == 8  # 2 L1 + 3 L2 + 3 L3
    assert stats.updated == 0
    codes = [
        c.code
        for c in sync_db.execute(select(Category).order_by(Category.code)).scalars()
    ]
    assert codes == [
        "01",
        "01.001",
        "01.001.001",
        "01.002",
        "01.002.001",
        "02",
        "02.001",
        "02.001.001",
    ]


def test_import_idempotent(sync_db):
    tree = _tree_with([("土建", "钢筋", ["螺纹钢"])])
    import_from_xlsx(sync_db, tree)
    sync_db.commit()

    stats = import_from_xlsx(sync_db, tree)
    sync_db.commit()
    assert stats.inserted == 0
    assert stats.updated == 0
    assert stats.kept == 0


def test_import_preserve_code_on_new_inserts(sync_db):
    """中间插新 L3,旧 code 不漂移,新节点拿空号。"""
    tree1 = _tree_with([("土建", "钢筋", ["螺纹钢", "圆钢"])])
    import_from_xlsx(sync_db, tree1)
    sync_db.commit()
    old = {
        c.name_zh: c.code for c in sync_db.execute(select(Category)).scalars()
    }

    tree2 = _tree_with([("土建", "钢筋", ["螺纹钢", "盘圆", "圆钢"])])
    stats = import_from_xlsx(sync_db, tree2)
    sync_db.commit()
    new = {
        c.name_zh: c.code for c in sync_db.execute(select(Category)).scalars()
    }
    assert stats.inserted == 1
    # 旧节点 code 沿用
    assert new["螺纹钢"] == old["螺纹钢"]
    assert new["圆钢"] == old["圆钢"]
    # 新节点拿空号(001/002 已占,取 003)
    assert new["盘圆"] == "01.001.003"


def test_import_same_name_under_different_parents(sync_db):
    """不同 parent 下同名 L3 是两个独立节点。"""
    tree = _tree_with(
        [
            ("土建", "钢筋", ["螺纹"]),
            ("土建", "商砼", ["螺纹"]),  # 同名,不同 parent
        ]
    )
    stats = import_from_xlsx(sync_db, tree)
    sync_db.commit()
    rows = sync_db.execute(
        select(Category).where(Category.name_zh == "螺纹")
    ).scalars().all()
    assert len(rows) == 2
    assert {r.parent_code for r in rows} == {"01.001", "01.002"}


def test_import_deactivate_missing(sync_db):
    tree1 = _tree_with([("土建", "钢筋", ["A", "B"])])
    import_from_xlsx(sync_db, tree1)
    sync_db.commit()

    tree2 = _tree_with([("土建", "钢筋", ["A"])])
    stats = import_from_xlsx(sync_db, tree2, deactivate_missing=True)
    sync_db.commit()
    assert stats.deactivated == 1
    b = sync_db.execute(
        select(Category).where(Category.name_zh == "B")
    ).scalar_one()
    assert b.is_active is False


def test_import_default_keep_missing(sync_db):
    """默认不停用 Excel 中缺失的节点。"""
    tree1 = _tree_with([("土建", "钢筋", ["A", "B"])])
    import_from_xlsx(sync_db, tree1)
    sync_db.commit()

    tree2 = _tree_with([("土建", "钢筋", ["A"])])
    stats = import_from_xlsx(sync_db, tree2)
    sync_db.commit()
    assert stats.kept == 1
    assert stats.deactivated == 0
    b = sync_db.execute(
        select(Category).where(Category.name_zh == "B")
    ).scalar_one()
    assert b.is_active is True


def test_import_dry_run_no_writes(sync_db):
    tree = _tree_with([("土建", "钢筋", ["螺纹钢"])])
    stats = import_from_xlsx(sync_db, tree, dry_run=True)
    sync_db.rollback()
    assert stats.inserted == 3
    assert sync_db.execute(select(Category)).scalars().all() == []


def test_import_reactivates_when_excel_has_it_again(sync_db):
    """先停用,再次出现在 Excel → is_active 重新 true。"""
    tree1 = _tree_with([("土建", "钢筋", ["A", "B"])])
    import_from_xlsx(sync_db, tree1)
    sync_db.commit()

    tree2 = _tree_with([("土建", "钢筋", ["A"])])
    import_from_xlsx(sync_db, tree2, deactivate_missing=True)
    sync_db.commit()

    # B 再次出现
    tree3 = _tree_with([("土建", "钢筋", ["A", "B"])])
    stats = import_from_xlsx(sync_db, tree3)
    sync_db.commit()
    assert stats.updated == 1
    b = sync_db.execute(
        select(Category).where(Category.name_zh == "B")
    ).scalar_one()
    assert b.is_active is True


# ---------- validate_xlsx_path ----------


def test_validate_xlsx_path_rejects_outside_data(tmp_path):
    p = tmp_path / "x.xlsx"
    p.write_bytes(b"fake")
    with pytest.raises(SystemExit):
        validate_xlsx_path(p)


def test_validate_xlsx_path_rejects_missing(tmp_path):
    with pytest.raises(SystemExit):
        validate_xlsx_path(tmp_path / "nope.xlsx")


def test_validate_xlsx_path_rejects_non_xlsx(tmp_path, monkeypatch):
    """非 .xlsx → fail-fast(monkeypatch 把 DATA_DIR 指到 tmp_path 以通过路径检查)。"""
    monkeypatch.setattr("scripts.import_categories.DATA_DIR", tmp_path)
    p = tmp_path / "x.csv"
    p.write_bytes(b"fake")
    with pytest.raises(SystemExit):
        validate_xlsx_path(p)
