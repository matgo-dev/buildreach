"""鑫方盛品类树全量导入 CLI 脚本。

用法
----
    # 从默认路径导入
    python scripts/import_categories_xfs.py

    # 显式指定文件
    python scripts/import_categories_xfs.py --file ../data/xfs/categories_full_tree.json

    # 只看差异不写库
    python scripts/import_categories_xfs.py --dry-run

设计要点
--------
- 独立于商品导入,只处理品类树
- 幂等:按 (name_zh, parent_code) 匹配现有节点,沿用 code
- L1 short_name 三语人工映射,标记 manual,翻译管道不覆盖
- name/name_en/name_sw 标记 pending,由翻译管道补译
- append-only,永不物理删除品类

⚠️ 本脚本**不在应用启动时自动跑**,只能本地/部署时人工执行。
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

# 让脚本能 import app.*
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.db.base import _utcnow  # noqa: E402
from app.db.models import Category  # noqa: E402
from app.db.url import prepare_sync_url  # noqa: E402

log = logging.getLogger(__name__)

PROJECT_ROOT = _BACKEND_ROOT.parent
DEFAULT_FILE = PROJECT_ROOT / "data" / "xfs" / "categories_full_tree.json"

# ────────────────────── L1 short_name 三语映射(人工校对) ──────────────────────

_L1_SHORT_NAME_I18N: dict[str, tuple[str, str]] = {
    "劳保": ("Safety", "Kinga"),
    "手动": ("Hand Tools", "Zana"),
    "紧固": ("Fastener", "Bolta"),
    "安防": ("Security", "Ulinzi"),
    "粘胶": ("Adhesive", "Gundi"),
    "气动": ("Pneumatic", "Hewa"),
    "磨具": ("Abrasive", "Sanifu"),
    "机电": ("Electro", "Umeme"),
    "五金": ("Hardware", "Vifaa"),
    "电器": ("Appliance", "Kifaa"),
    "灯具": ("Lighting", "Taa"),
    "电缆": ("Cable", "Kebo"),
    "电力": ("Conduit", "Njia"),
    "工控": ("Automate", "Kiwanda"),
    "电辅": ("Wiring", "Nyaya"),
    "保温": ("Insulate", "Joto"),
    "防水": ("Waterproof", "Sifongo"),
    "涂料": ("Paint", "Rangi"),
    "装饰": ("Decor", "Mapambo"),
    "门窗": ("Door&Win", "Milango"),
    "土建": ("Civil", "Ujenzi"),
    "临建": ("Temp Build", "Kambi"),
    "装配": ("Precast", "Paneli"),
    "暖通": ("HVAC", "HVAC"),
    "水暖": ("Plumbing", "Paipu"),
    "消防": ("Fire", "Zimamoto"),
    "陶瓷": ("Sanitary", "Vyoo"),
    "管道": ("Piping", "Mirija"),
    "量具": ("Measure", "Kipimo"),
    "金属": ("Metal", "Metali"),
    "配电": ("Switchgear", "Gridi"),
}


# ────────────────────── 数据结构 ──────────────────────


@dataclass
class CategoryNode:
    """品类树节点。"""
    name_zh: str
    level: int
    path_zh: str = ""
    short_name: str | None = None
    parent_name_zh: str | None = None
    children: list["CategoryNode"] = field(default_factory=list)
    db_code: str | None = None


# ────────────────────── 树构建 ──────────────────────


def build_category_tree(raw: list) -> list[CategoryNode]:
    """从扁平数组构建品类树。

    支持两种 path_zh 分隔符:> (新版) 和 / (旧版)。
    父子挂载策略:path_zh 截取 > parent_zh 查找 > level 栈式推断。
    """
    nodes_by_path: dict[str, CategoryNode] = {}
    nodes_by_name: dict[str, CategoryNode] = {}
    all_nodes: list[CategoryNode] = []

    for item in raw:
        name_zh = item.get("name_zh", "")
        path_zh = item.get("path_zh", "")
        node = CategoryNode(
            name_zh=name_zh,
            level=item.get("level", 1),
            path_zh=path_zh or name_zh,
            short_name=item.get("short_name"),
            parent_name_zh=item.get("parent_zh"),
        )
        if path_zh:
            nodes_by_path[path_zh] = node
        nodes_by_name[name_zh] = node
        all_nodes.append(node)

    # 自动检测分隔符
    _sep = ">"
    if not any(">" in (n.path_zh or "") for n in all_nodes):
        _sep = "/"
    has_path_zh = any(n.path_zh and _sep in n.path_zh for n in all_nodes)
    has_parent_refs = any(n.parent_name_zh for n in all_nodes)

    roots: list[CategoryNode] = []

    if has_path_zh:
        orphans: list[CategoryNode] = []
        for node in all_nodes:
            if _sep not in node.path_zh:
                roots.append(node)
            else:
                parent_path = node.path_zh.rsplit(_sep, 1)[0]
                parent = nodes_by_path.get(parent_path)
                if parent:
                    parent.children.append(node)
                else:
                    orphans.append(node)
        if orphans:
            log.error("%d 个品类节点无法通过 path_zh 找到父节点:", len(orphans))
            for o in orphans[:20]:
                log.error("  path_zh=%s  name_zh=%s", o.path_zh, o.name_zh)
            raise ValueError(f"{len(orphans)} 个品类 path_zh 解析失败")
    elif has_parent_refs:
        for node in all_nodes:
            if not node.parent_name_zh:
                roots.append(node)
            else:
                parent = nodes_by_name.get(node.parent_name_zh)
                if parent:
                    parent.children.append(node)
                else:
                    roots.append(node)
    else:
        # level 栈式推断
        stack: list[CategoryNode] = []
        for node in all_nodes:
            while stack and stack[-1].level >= node.level:
                stack.pop()
            if stack:
                stack[-1].children.append(node)
            else:
                roots.append(node)
            stack.append(node)

    log.info("品类树: %d 个根节点, %d 个总节点", len(roots), len(all_nodes))
    return roots


# ────────────────────── code 生成 ──────────────────────


def _split_seq(code: str) -> int:
    return int(code.split(".")[-1])


def _next_seq(used: set[int]) -> int:
    seq = 1
    while seq in used:
        seq += 1
    return seq


def _make_code(parent_code: str | None, seq: int, level: int) -> str:
    """L1 两位,L2+ 三位,父子用点分隔。"""
    if level == 1:
        return f"{seq:02d}"
    assert parent_code is not None
    return f"{parent_code}.{seq:03d}"


# ────────────────────── 导入主逻辑 ──────────────────────


def import_categories(db: Session, cat_tree: list[CategoryNode]) -> dict[str, str]:
    """将品类树全量写入 categories 表,返回 path_zh → code 映射。

    按 (name_zh, parent_code) 匹配现有节点,沿用 code;
    新节点取空号生成稳定 code。append-only,永不物理删。
    """
    existing_by_natural: dict[tuple[str, str | None], Category] = {}
    used_seq_by_parent: dict[str | None, set[int]] = {}

    for c in db.execute(select(Category)).scalars().all():
        existing_by_natural[(c.name_zh, c.parent_code)] = c
        used_seq_by_parent.setdefault(c.parent_code, set()).add(_split_seq(c.code))

    path_to_code: dict[str, str] = {}
    _name_codes: dict[str, str | None] = {}
    inserted = 0
    updated = 0

    def _upsert_node(node: CategoryNode, parent_code: str | None) -> str:
        nonlocal inserted, updated

        natural_key = (node.name_zh, parent_code)
        existing = existing_by_natural.get(natural_key)

        if existing:
            code = existing.code
            changed = False
            if existing.level != node.level:
                existing.level = node.level
                changed = True
            if not existing.is_active:
                existing.is_active = True
                changed = True
            if node.short_name and existing.short_name_zh != node.short_name:
                existing.short_name_zh = node.short_name
                changed = True
            # 补齐 L1 short_name en/sw
            if node.short_name and node.short_name in _L1_SHORT_NAME_I18N:
                sn_en, sn_sw = _L1_SHORT_NAME_I18N[node.short_name]
                if existing.short_name_en != sn_en:
                    existing.short_name_en = sn_en
                    changed = True
                if existing.short_name_sw != sn_sw:
                    existing.short_name_sw = sn_sw
                    changed = True
                meta = dict(existing.trans_meta or {})
                if meta.get("short_name_en") != "manual" or meta.get("short_name_sw") != "manual":
                    meta["short_name_en"] = "manual"
                    meta["short_name_sw"] = "manual"
                    existing.trans_meta = meta
                    changed = True
            if changed:
                existing.updated_at = _utcnow()
                updated += 1
        else:
            used = used_seq_by_parent.setdefault(parent_code, set())
            seq = _next_seq(used)
            used.add(seq)
            code = _make_code(parent_code, seq, node.level)

            now = _utcnow()
            sn_en, sn_sw = None, None
            sn_en_status, sn_sw_status = "pending", "pending"
            if node.short_name and node.short_name in _L1_SHORT_NAME_I18N:
                sn_en, sn_sw = _L1_SHORT_NAME_I18N[node.short_name]
                sn_en_status, sn_sw_status = "manual", "manual"

            cat = Category(
                code=code,
                name_zh=node.name_zh,
                name_en=None,
                short_name_zh=node.short_name,
                short_name_en=sn_en,
                short_name_sw=sn_sw,
                level=node.level,
                parent_code=parent_code,
                sort_order=0,
                is_active=True,
                created_at=now,
                updated_at=now,
                source_lang="zh",
                trans_meta={
                    "name_zh": "src",
                    "name_en": "pending",
                    "name_sw": "pending",
                    "short_name_zh": "src" if node.short_name else None,
                    "short_name_en": sn_en_status if node.short_name else None,
                    "short_name_sw": sn_sw_status if node.short_name else None,
                },
                i18n_pending_at=now,
            )
            db.add(cat)
            db.flush()
            existing_by_natural[natural_key] = cat
            inserted += 1

        if node.path_zh:
            path_to_code[node.path_zh] = code
        if node.name_zh in _name_codes:
            if _name_codes[node.name_zh] != code:
                _name_codes[node.name_zh] = None
        else:
            _name_codes[node.name_zh] = code
        node.db_code = code

        for child in node.children:
            _upsert_node(child, code)

        return code

    for root in cat_tree:
        _upsert_node(root, None)

    # 无冲突的 name_zh 也写入映射
    for name, code in _name_codes.items():
        if code is not None and name not in path_to_code:
            path_to_code[name] = code

    # 刷新 is_leaf
    all_cats = db.execute(select(Category)).scalars().all()
    parent_codes_with_active_children: set[str] = set()
    for c in all_cats:
        if c.parent_code and c.is_active:
            parent_codes_with_active_children.add(c.parent_code)
    for c in all_cats:
        c.is_leaf = c.code not in parent_codes_with_active_children

    log.info("品类导入完成: 新增=%d, 更新=%d, 总映射=%d", inserted, updated, len(path_to_code))
    return path_to_code


# ────────────────────── CLI ──────────────────────


def main():
    parser = argparse.ArgumentParser(description="鑫方盛品类树全量导入")
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE, help="品类 JSON 文件路径")
    parser.add_argument("--dry-run", action="store_true", help="只解析不写库")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    if not args.file.exists():
        log.error("品类文件不存在: %s", args.file)
        sys.exit(1)

    raw = json.loads(args.file.read_text(encoding="utf-8"))
    log.info("读取品类数据: %d 条, 来源: %s", len(raw), args.file.name)

    tree = build_category_tree(raw)

    if args.dry_run:
        # 统计各级数量
        def _count(nodes: list[CategoryNode], depth: int = 1) -> dict[int, int]:
            counts: dict[int, int] = {}
            for n in nodes:
                counts[depth] = counts.get(depth, 0) + 1
                for k, v in _count(n.children, depth + 1).items():
                    counts[k] = counts.get(k, 0) + v
            return counts

        level_counts = _count(tree)
        for lvl in sorted(level_counts):
            log.info("  L%d: %d 个", lvl, level_counts[lvl])
        log.info("dry-run 完成,未写库")
        return

    sync_url = prepare_sync_url(str(settings.DATABASE_URL))
    engine = create_engine(sync_url, echo=False)

    with Session(engine) as db:
        import_categories(db, tree)
        db.commit()
        log.info("事务已提交")


if __name__ == "__main__":
    main()
