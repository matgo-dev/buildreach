"""品类声明式治理 — 从 data/categories.csv 导入/更新品类表。

用法
----
    # 默认读 data/categories.csv,对比 DB 做 upsert
    python scripts/import_categories.py

    # 只看差异不写库
    python scripts/import_categories.py --dry-run

    # 把 DB 里有但 CSV 没有的分类置 is_active=false
    python scripts/import_categories.py --deactivate-missing

设计要点
--------
- CSV 是品类的唯一权威来源(声明式):code 是主键,永不由脚本生成
- 以 code 为主键做 upsert:存在→更新名称字段,不存在→插入
- CSV 多出 short_name_*/is_leaf 列,模型无对应字段,直接忽略
- 保留 trans_meta / i18n_pending_at 逻辑:新建节点标 pending,更新仅改名称列时不触发重译
- 永不物理删,停用走 is_active=false(需加 --deactivate-missing)
- --dry-run 只打印差异,不写库

⚠️ 本脚本**不在应用启动时自动跑**,只能人工执行。
"""
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.db.base import _utcnow  # noqa: E402
from app.db.models import Category  # noqa: E402
from app.db.url import prepare_sync_url  # noqa: E402

PROJECT_ROOT = _BACKEND_ROOT.parent
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_CSV = DATA_DIR / "categories.csv"

# CSV 中必须存在的列
REQUIRED_COLS = {"code", "level", "name_zh", "parent_code", "is_active"}


# ────────────────────── 数据结构 ──────────────────────


@dataclass
class CsvRow:
    """一行 CSV 解析结果,只保留 Category 模型有对应字段的值。"""
    code: str
    level: int
    name_zh: str
    name_en: str | None
    name_sw: str | None
    parent_code: str | None
    is_active: bool


@dataclass
class ImportStats:
    inserted: int = 0
    updated: int = 0
    kept: int = 0          # DB 有但 CSV 无,默认保留
    deactivated: int = 0

    inserted_codes: list[str] = field(default_factory=list)
    deactivated_codes: list[str] = field(default_factory=list)


# ────────────────────── CSV 解析 ──────────────────────


def parse_csv(path: Path) -> list[CsvRow]:
    """读取 CSV,校验必要列,返回解析好的行列表。

    忽略 short_name_* / is_leaf 等模型无对应字段的列。
    """
    if not path.exists():
        sys.exit(f"[ERROR] CSV 文件不存在: {path}")

    rows: list[CsvRow] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            sys.exit("[ERROR] CSV 文件为空")

        # 校验必要列齐全
        actual_cols = set(reader.fieldnames)
        missing = REQUIRED_COLS - actual_cols
        if missing:
            sys.exit(f"[ERROR] CSV 缺少必要列: {sorted(missing)}")

        for line_no, raw in enumerate(reader, start=2):
            code = raw.get("code", "").strip()
            if not code:
                print(f"[WARN] 第 {line_no} 行 code 为空,跳过")
                continue

            try:
                level = int(raw.get("level") or 0)
            except ValueError:
                sys.exit(f"[ERROR] 第 {line_no} 行 level 非整数: {raw.get('level')}")

            if level < 1:
                sys.exit(f"[ERROR] 第 {line_no} 行 level 无效(必须 >= 1): {level}")

            parent_code = raw.get("parent_code", "").strip() or None
            name_zh = raw.get("name_zh", "").strip()
            if not name_zh:
                sys.exit(f"[ERROR] 第 {line_no} 行 name_zh 为空,code={code}")

            name_en = raw.get("name_en", "").strip() or None
            name_sw = raw.get("name_sw", "").strip() or None

            # 生产库导出的 bool 值为 't'/'f'
            is_active_raw = raw.get("is_active", "t").strip().lower()
            is_active = is_active_raw not in ("f", "false", "0", "no")

            rows.append(CsvRow(
                code=code,
                level=level,
                name_zh=name_zh,
                name_en=name_en,
                name_sw=name_sw,
                parent_code=parent_code,
                is_active=is_active,
            ))

    return rows


# ────────────────────── 核心导入 ──────────────────────


def _names_differ(cat: Category, row: CsvRow) -> bool:
    """判断名称字段是否有变化。"""
    return (
        cat.name_zh != row.name_zh
        or cat.name_en != row.name_en
        or cat.name_sw != row.name_sw
    )


def import_from_csv(
    db: Session,
    rows: list[CsvRow],
    dry_run: bool = False,
    deactivate_missing: bool = False,
) -> ImportStats:
    """核心算法:以 code 为主键做 upsert。

    不生成 code,code 全部来自 CSV。
    """
    stats = ImportStats()

    # 加载 DB 全量品类,按 code 索引
    existing_by_code: dict[str, Category] = {
        c.code: c
        for c in db.execute(select(Category)).scalars().all()
    }

    csv_codes: set[str] = set()

    for row in rows:
        csv_codes.add(row.code)
        existing = existing_by_code.get(row.code)

        if existing:
            # 已存在:检查名称字段是否变化
            names_changed = _names_differ(existing, row)
            # 检查 is_active 是否需要恢复(CSV 标活跃但 DB 是停用)
            active_changed = row.is_active and not existing.is_active

            changed = names_changed or active_changed

            if changed:
                stats.updated += 1
                if not dry_run:
                    existing.name_zh = row.name_zh
                    existing.name_en = row.name_en
                    existing.name_sw = row.name_sw
                    existing.is_active = row.is_active
                    existing.updated_at = _utcnow()
                    # 名称变化时触发翻译重译:把 pending 字段重新标记
                    if names_changed:
                        meta = dict(existing.trans_meta or {})
                        if row.name_en:
                            meta["name_en"] = "manual"
                        else:
                            meta["name_en"] = "pending"
                        if row.name_sw:
                            meta["name_sw"] = "manual"
                        else:
                            meta["name_sw"] = "pending"
                        existing.trans_meta = meta
                        existing.i18n_pending_at = _utcnow()
        else:
            # 新建:code 直接来自 CSV,不自动生成
            stats.inserted += 1
            stats.inserted_codes.append(row.code)
            if not dry_run:
                now = _utcnow()
                # 根据 CSV 中哪些语言列有值决定 trans_meta 状态
                trans_meta: dict[str, str] = {"name_zh": "src"}
                trans_meta["name_en"] = "manual" if row.name_en else "pending"
                trans_meta["name_sw"] = "manual" if row.name_sw else "pending"

                db.add(Category(
                    code=row.code,
                    name_zh=row.name_zh,
                    name_en=row.name_en,
                    name_sw=row.name_sw,
                    level=row.level,
                    parent_code=row.parent_code,
                    sort_order=0,
                    is_active=row.is_active,
                    created_at=now,
                    updated_at=now,
                    source_lang="zh",
                    trans_meta=trans_meta,
                    i18n_pending_at=now,
                ))

    # 处理 DB 有但 CSV 没有的节点
    for code, cat in existing_by_code.items():
        if code in csv_codes:
            continue
        if deactivate_missing:
            stats.deactivated += 1
            stats.deactivated_codes.append(code)
            if not dry_run and cat.is_active:
                cat.is_active = False
                cat.updated_at = _utcnow()
        else:
            stats.kept += 1

    # 全量刷新 is_leaf:有 active 子节点的品类为非叶子
    if not dry_run:
        _sync_is_leaf(db)

    return stats


def _sync_is_leaf(db: Session) -> None:
    """全量刷新所有品类的 is_leaf 标记。"""
    all_cats = db.execute(select(Category)).scalars().all()
    parent_codes_with_active_children: set[str] = set()
    for cat in all_cats:
        if cat.parent_code and cat.is_active:
            parent_codes_with_active_children.add(cat.parent_code)
    for cat in all_cats:
        cat.is_leaf = cat.code not in parent_codes_with_active_children


# ────────────────────── CLI ──────────────────────


def _print_stats(stats: ImportStats, dry_run: bool) -> None:
    title = "DRY RUN 差异统计" if dry_run else "导入结果"
    print(f"--- {title} ---")
    print(f"新增   : {stats.inserted}")
    print(f"更新   : {stats.updated}")
    print(
        f"保留不动: {stats.kept}    (DB 有但 CSV 无;加 --deactivate-missing 将停用)"
    )
    print(f"将停用 : {stats.deactivated}")
    if stats.inserted_codes:
        n = min(10, len(stats.inserted_codes))
        more = (
            f"  ... (+{len(stats.inserted_codes) - n})"
            if len(stats.inserted_codes) > n
            else ""
        )
        print(f"  新增 codes 样例: {stats.inserted_codes[:n]}{more}")
    if stats.deactivated_codes:
        n = min(10, len(stats.deactivated_codes))
        more = (
            f"  ... (+{len(stats.deactivated_codes) - n})"
            if len(stats.deactivated_codes) > n
            else ""
        )
        print(f"  停用 codes 样例: {stats.deactivated_codes[:n]}{more}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="品类声明式治理 — 从 data/categories.csv 导入/更新品类表"
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_CSV,
        help=f"CSV 文件路径(默认: {DEFAULT_CSV})",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="只打印差异统计,不写库"
    )
    parser.add_argument(
        "--deactivate-missing",
        action="store_true",
        help="把 DB 里有但 CSV 没有的分类置 is_active=false",
    )
    args = parser.parse_args()

    csv_path = args.file.resolve()
    print(f"[INFO] CSV: {csv_path}")
    print(
        f"[INFO] dry-run={args.dry_run}, deactivate-missing={args.deactivate_missing}"
    )

    rows = parse_csv(csv_path)
    print(f"[INFO] CSV 行数: {len(rows)}")

    sync_url = prepare_sync_url(settings.DATABASE_URL)
    engine = create_engine(sync_url)
    with Session(engine) as db:
        stats = import_from_csv(
            db,
            rows,
            dry_run=args.dry_run,
            deactivate_missing=args.deactivate_missing,
        )
        if args.dry_run:
            db.rollback()
            print("[DRY RUN] 未写库,事务已 rollback")
        else:
            db.commit()
            print("[OK] 已 commit")

    _print_stats(stats, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
