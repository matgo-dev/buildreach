"""CSV 品类导入脚本测试(对齐 scripts/import_categories.py 声明式治理版本)。

脚本本身用 sync SQLAlchemy(psycopg),所以不依赖 conftest 的 async fixture,
独立建 sync engine 跑测试。drop_all + create_all 每个 test 隔离。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.base import Base
from app.db import models as _models  # noqa: F401
from app.db.models import Category
from app.db.url import prepare_sync_url
from scripts.import_categories import (
    CsvRow,
    ImportStats,
    import_from_csv,
    parse_csv,
)


TEST_DSN = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://liujingjing@localhost:5433/overseas_supply_test",
)
SYNC_DSN = prepare_sync_url(TEST_DSN)


# ---------- fixture: sync session ----------


@pytest.fixture
def sync_db():
    """同步 session，用于测试 sync 导入脚本。

    使用 SAVEPOINT 隔离：不破坏 session-scope 的 async _engine schema 和 seed 数据，
    测后回滚恢复。先 TRUNCATE categories/attr_templates 清除 seed，在 SAVEPOINT 内操作。
    """
    from sqlalchemy import event, text

    engine = create_engine(SYNC_DSN, poolclass=None)
    conn = engine.connect()
    txn = conn.begin()
    # 在外层事务内清空品类，给 import 脚本一个干净的起点
    conn.execute(text("TRUNCATE categories, attr_templates RESTART IDENTITY CASCADE"))
    conn.begin_nested()  # SAVEPOINT
    session = Session(bind=conn)

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, transaction):
        if transaction.nested and not transaction._parent.nested:
            sess.begin_nested()

    yield session

    session.close()
    txn.rollback()  # 回滚外层事务，恢复 seed 数据
    conn.close()
    engine.dispose()


# ---------- helpers ----------


def _make_csv(tmp_path: Path, rows: list[dict], name: str = "cat.csv") -> Path:
    """生成测试用 CSV 文件。"""
    header = "code,level,name_zh,name_en,name_sw,short_name_zh,short_name_en,short_name_sw,parent_code,is_leaf,is_active"
    lines = [header]
    for r in rows:
        lines.append(",".join([
            r.get("code", ""),
            str(r.get("level", 1)),
            r.get("name_zh", ""),
            r.get("name_en", ""),
            r.get("name_sw", ""),
            r.get("short_name_zh", ""),
            r.get("short_name_en", ""),
            r.get("short_name_sw", ""),
            r.get("parent_code", ""),
            r.get("is_leaf", "f"),
            r.get("is_active", "t"),
        ]))
    path = tmp_path / name
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _rows_for(*specs: tuple[str, int, str, str]) -> list[CsvRow]:
    """快速构造 CsvRow 列表: (code, level, name_zh, parent_code)。"""
    return [
        CsvRow(
            code=code,
            level=level,
            name_zh=name_zh,
            name_en=None,
            name_sw=None,
            parent_code=parent_code or None,
            is_active=True,
        )
        for code, level, name_zh, parent_code in specs
    ]


# ---------- parse_csv ----------


def test_parse_csv_basic(tmp_path):
    rows = _make_csv(tmp_path, [
        {"code": "01", "level": "1", "name_zh": "土建", "parent_code": "", "is_leaf": "f", "is_active": "t"},
        {"code": "01.001", "level": "2", "name_zh": "钢筋", "parent_code": "01", "is_leaf": "t", "is_active": "t"},
    ])
    result = parse_csv(rows)
    assert len(result) == 2
    assert result[0].code == "01"
    assert result[0].level == 1
    assert result[1].parent_code == "01"


def test_parse_csv_bool_parsing(tmp_path):
    """PostgreSQL 布尔值 t/f 正确解析。"""
    rows = _make_csv(tmp_path, [
        {"code": "01", "level": "1", "name_zh": "X", "is_active": "t"},
        {"code": "02", "level": "1", "name_zh": "Y", "is_active": "f"},
    ])
    result = parse_csv(rows)
    assert result[0].is_active is True
    assert result[1].is_active is False


def test_parse_csv_missing_required_col(tmp_path):
    """缺少必要列 → fail-fast。"""
    path = tmp_path / "bad.csv"
    path.write_text("code,level,name_zh\n01,1,X\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        parse_csv(path)


def test_parse_csv_empty_code_skipped(tmp_path):
    """空 code 行被跳过。"""
    rows = _make_csv(tmp_path, [
        {"code": "01", "level": "1", "name_zh": "A", "parent_code": "", "is_active": "t"},
        {"code": "", "level": "1", "name_zh": "B", "parent_code": "", "is_active": "t"},
    ])
    result = parse_csv(rows)
    assert len(result) == 1


def test_parse_csv_name_en_sw_nullable(tmp_path):
    """name_en/name_sw 为空时解析为 None。"""
    rows = _make_csv(tmp_path, [
        {"code": "01", "level": "1", "name_zh": "X", "name_en": "", "name_sw": ""},
    ])
    result = parse_csv(rows)
    assert result[0].name_en is None
    assert result[0].name_sw is None


# ---------- import_from_csv 核心算法 ----------


def test_import_empty_db_all_new(sync_db):
    rows = _rows_for(
        ("01", 1, "土建", ""),
        ("01.001", 2, "钢筋", "01"),
        ("01.001.001", 3, "螺纹钢", "01.001"),
        ("02", 1, "安装", ""),
    )
    stats = import_from_csv(sync_db, rows)
    sync_db.commit()
    assert stats.inserted == 4
    assert stats.updated == 0
    codes = [
        c.code
        for c in sync_db.execute(select(Category).order_by(Category.code)).scalars()
    ]
    assert codes == ["01", "01.001", "01.001.001", "02"]


def test_import_idempotent(sync_db):
    rows = _rows_for(
        ("01", 1, "土建", ""),
        ("01.001", 2, "钢筋", "01"),
    )
    import_from_csv(sync_db, rows)
    sync_db.commit()

    stats = import_from_csv(sync_db, rows)
    sync_db.commit()
    assert stats.inserted == 0
    assert stats.updated == 0


def test_import_preserves_code(sync_db):
    """CSV 中的 code 原样写入 DB，不做任何生成。"""
    rows = _rows_for(
        ("99", 1, "特殊", ""),
        ("99.888", 2, "子类", "99"),
    )
    stats = import_from_csv(sync_db, rows)
    sync_db.commit()
    assert stats.inserted == 2
    codes = {
        c.code
        for c in sync_db.execute(select(Category)).scalars()
    }
    assert "99" in codes
    assert "99.888" in codes


def test_import_updates_name(sync_db):
    """名称变化时触发更新。"""
    rows1 = _rows_for(("01", 1, "土建", ""))
    import_from_csv(sync_db, rows1)
    sync_db.commit()

    rows2 = [CsvRow(code="01", level=1, name_zh="土建材料", name_en="Civil", name_sw=None, parent_code=None, is_active=True)]
    stats = import_from_csv(sync_db, rows2)
    sync_db.commit()
    assert stats.updated == 1
    cat = sync_db.execute(select(Category).where(Category.code == "01")).scalar_one()
    assert cat.name_zh == "土建材料"
    assert cat.name_en == "Civil"


def test_import_deactivate_missing(sync_db):
    rows1 = _rows_for(
        ("01", 1, "A", ""),
        ("02", 1, "B", ""),
    )
    import_from_csv(sync_db, rows1)
    sync_db.commit()

    rows2 = _rows_for(("01", 1, "A", ""))
    stats = import_from_csv(sync_db, rows2, deactivate_missing=True)
    sync_db.commit()
    assert stats.deactivated == 1
    b = sync_db.execute(select(Category).where(Category.code == "02")).scalar_one()
    assert b.is_active is False


def test_import_default_keep_missing(sync_db):
    """默认不停用 CSV 中缺失的节点。"""
    rows1 = _rows_for(
        ("01", 1, "A", ""),
        ("02", 1, "B", ""),
    )
    import_from_csv(sync_db, rows1)
    sync_db.commit()

    rows2 = _rows_for(("01", 1, "A", ""))
    stats = import_from_csv(sync_db, rows2)
    sync_db.commit()
    assert stats.kept == 1
    assert stats.deactivated == 0
    b = sync_db.execute(select(Category).where(Category.code == "02")).scalar_one()
    assert b.is_active is True


def test_import_dry_run_no_writes(sync_db):
    rows = _rows_for(("01", 1, "土建", ""))
    stats = import_from_csv(sync_db, rows, dry_run=True)
    sync_db.rollback()
    assert stats.inserted == 1
    assert sync_db.execute(select(Category)).scalars().all() == []


def test_import_reactivates_when_csv_has_it_again(sync_db):
    """先停用，再次出现在 CSV → is_active 重新 true。"""
    rows1 = _rows_for(
        ("01", 1, "A", ""),
        ("02", 1, "B", ""),
    )
    import_from_csv(sync_db, rows1)
    sync_db.commit()

    rows2 = _rows_for(("01", 1, "A", ""))
    import_from_csv(sync_db, rows2, deactivate_missing=True)
    sync_db.commit()

    # B 再次出现
    rows3 = _rows_for(
        ("01", 1, "A", ""),
        ("02", 1, "B", ""),
    )
    stats = import_from_csv(sync_db, rows3)
    sync_db.commit()
    assert stats.updated == 1
    b = sync_db.execute(select(Category).where(Category.code == "02")).scalar_one()
    assert b.is_active is True


def test_import_is_leaf_synced(sync_db):
    """导入后 is_leaf 自动刷新：有子节点的标 False，叶子标 True。"""
    rows = _rows_for(
        ("01", 1, "Parent", ""),
        ("01.001", 2, "Child", "01"),
    )
    import_from_csv(sync_db, rows)
    sync_db.commit()
    parent = sync_db.execute(select(Category).where(Category.code == "01")).scalar_one()
    child = sync_db.execute(select(Category).where(Category.code == "01.001")).scalar_one()
    assert parent.is_leaf is False
    assert child.is_leaf is True


def test_import_trans_meta_new_node(sync_db):
    """新建节点的 trans_meta 根据 CSV 有无值正确标记。"""
    rows = [CsvRow(code="01", level=1, name_zh="X", name_en="Y", name_sw=None, parent_code=None, is_active=True)]
    import_from_csv(sync_db, rows)
    sync_db.commit()
    cat = sync_db.execute(select(Category).where(Category.code == "01")).scalar_one()
    assert cat.trans_meta["name_en"] == "manual"
    assert cat.trans_meta["name_sw"] == "pending"
