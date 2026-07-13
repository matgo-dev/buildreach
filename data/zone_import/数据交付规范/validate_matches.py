#!/usr/bin/env python3
"""央企专区交付自校验脚本 —— 数据提供方发货前自己先跑,过了再发。

用法:
    python validate_matches.py <交付目录>
    # 交付目录里需有 matches.json 和 images/;白名单与本脚本同目录

它检查三件每批都会翻车的事:
  1. 结构:matches.json 是数组、必填字段齐、matched_category_path 是【数组】不是字符串。
  2. 分类可落:每条的 matched_category_path 能在我方【类目白名单】里逐级命中到叶子;
     或提供的 matched_leaf_code 在白名单里。命不中的逐条列出(这些回挂时分类会挂不上)。
  3. 图片:引用的图片文件真实存在。

退出码非 0 = 有硬问题,别发货。
"""
from __future__ import annotations
import csv, json, re, sys, unicodedata
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
WHITELIST = HERE / "类目白名单_叶子.csv"

def hard(s: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(s or "")))

def load_tree():
    """返回 (按父+名下钻的索引, 叶子code集合, code->路径)。"""
    by_parent: dict[tuple[str, str], str] = {}
    parent_of: dict[str, str] = {}
    name_of: dict[str, str] = {}
    children: dict[str, int] = defaultdict(int)
    leaf_codes: set[str] = set()
    with WHITELIST.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            leaf_codes.add(r["leaf_code"])
    # 白名单只有叶子+路径;从路径重建逐级索引
    with WHITELIST.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            segs = [s.strip() for s in r["category_path"].split(" / ")]
            parent = ""
            code_parts = r["leaf_code"].split(".")
            for i, nm in enumerate(segs):
                code = ".".join(code_parts[: i + 1])
                by_parent[(parent, hard(nm))] = code
                name_of[code] = nm
                parent_of[code] = parent
                parent = code
    return by_parent, leaf_codes, name_of

def resolve(path_list, by_parent, leaf_codes) -> tuple[str, str]:
    parent = ""; depth = 0; last = None
    for nm in path_list:
        k = (parent, hard(nm))
        if k not in by_parent:
            if depth == 0:
                return "no_L1", nm
            return "broke_at", nm
        last = by_parent[k]; parent = last; depth += 1
    return ("leaf_ok" if last in leaf_codes else "nonleaf"), (last or "")

def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python validate_matches.py <交付目录>"); return 2
    src = Path(sys.argv[1])
    mj = src / "matches.json"
    if not mj.exists():
        print(f"✗ 找不到 {mj}"); return 2
    if not WHITELIST.exists():
        print(f"✗ 找不到类目白名单 {WHITELIST}"); return 2

    try:
        data = json.loads(mj.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"✗ matches.json 不是合法 JSON: {e}"); return 2
    if not isinstance(data, list):
        print("✗ matches.json 顶层必须是数组"); return 2

    by_parent, leaf_codes, _ = load_tree()
    hard_errs, struct, no_l1, nonleaf, broke, img_miss, ok = [], [], [], [], [], [], 0
    REQ = ("offer_id", "material_name", "material_category_code", "matched_category_path", "images")

    for i, r in enumerate(data, 1):
        tag = f"#{i} offer={r.get('offer_id','?')} {r.get('material_name','?')}"
        if not isinstance(r, dict):
            hard_errs.append(f"{tag}: 不是对象"); continue
        for k in REQ:
            if k not in r:
                struct.append(f"{tag}: 缺字段 {k}")
        mcp = r.get("matched_category_path")
        if isinstance(mcp, str):
            hard_errs.append(f"{tag}: matched_category_path 是字符串,必须是数组")
            mcp = None
        # 图片存在性
        imgs = r.get("images") or {}
        for kind in ("main", "gallery", "detail"):
            for rel in (imgs.get(kind) or []):
                if not (src / rel).exists():
                    img_miss.append(f"{tag}: 缺图 {rel}")
        # 分类可落
        leaf_code = r.get("matched_leaf_code")
        if leaf_code:
            if leaf_code not in leaf_codes:
                no_l1.append(f"{tag}: matched_leaf_code 不在白名单 {leaf_code}")
            else:
                ok += 1
        elif isinstance(mcp, list) and mcp:
            st, extra = resolve([str(x) for x in mcp], by_parent, leaf_codes)
            if st == "leaf_ok": ok += 1
            elif st == "no_L1": no_l1.append(f"{tag}: 一级不在白名单 → {extra}  (path={' / '.join(map(str,mcp))})")
            elif st == "broke_at": broke.append(f"{tag}: 断在 '{extra}'  (path={' / '.join(map(str,mcp))})")
            else: nonleaf.append(f"{tag}: 落到非叶子  (path={' / '.join(map(str,mcp))})")
        else:
            no_l1.append(f"{tag}: matched_category_path 空,分类待定")

    n = len(data)
    print("=" * 64)
    print(f"交付自校验  共 {n} 条")
    print("=" * 64)
    print(f"分类可落到叶子:      {ok}")
    print(f"一级/叶子不在白名单: {len(no_l1)}   ← 分类会挂不上,请改映射到白名单")
    print(f"中途断级:            {len(broke)}")
    print(f"落非叶子:            {len(nonleaf)}")
    print(f"缺图文件:            {len(img_miss)}")
    print(f"结构缺字段:          {len(struct)}")
    print(f"硬错(格式):          {len(hard_errs)}")
    def dump(title, items):
        if items:
            print(f"\n--- {title} ({len(items)}) ---")
            for x in items[:40]: print("  " + x)
            if len(items) > 40: print(f"  ... 还有 {len(items)-40} 条")
    dump("硬错·格式(必修)", hard_errs)
    dump("结构缺字段(必修)", struct)
    dump("一级不在白名单(需改映射)", no_l1)
    dump("中途断级", broke)
    dump("落非叶子", nonleaf)
    dump("缺图", img_miss)

    fatal = hard_errs or struct or img_miss
    print("\n" + ("✗ 有硬问题,不要发货,修完再跑。" if fatal else
                   ("⚠ 结构/图片 OK,但有分类挂不上的条目,尽量改到白名单;可发但会有部分不回写分类。"
                    if no_l1 or broke or nonleaf else "✓ 全部通过,可发货。")))
    return 1 if fatal else 0

if __name__ == "__main__":
    sys.exit(main())
