import json
from pathlib import Path

from scripts.import_zone_soe_images_matches import (
    ImageIn,
    _hard,
    _raw_url,
    _should_hold_low_res,
    load_decisions,
    load_input_rows,
    resolve_spu_code,
    zsoe_spu_code,
)


def test_raw_url_strips_oss_process_query():
    assert _raw_url(
        "https://fsyuncai.oss-cn-beijing.aliyuncs.com/a/b.jpg?x-oss-process=style/marking_detail"
    ) == "https://fsyuncai.oss-cn-beijing.aliyuncs.com/a/b.jpg"


def test_load_matches_json_preferred_shape(tmp_path: Path):
    (tmp_path / "images" / "19396354").mkdir(parents=True)
    (tmp_path / "images" / "19396354" / "main_01.jpg").write_bytes(b"x")
    (tmp_path / "matches.json").write_text(json.dumps([{
        "material_category_code": "02",
        "material_category_name": "水泥类",
        "material_name": "水泥",
        "offer_id": "19396354",
        "offer_url": "https://www.xfs.com/productsku/19396354.html",
        "listing_title": "洪双竹 PC325/PF325水泥 50kg",
        "matched_category_path": ["涂料化工", "墙地面", "砂石水泥", "水泥"],
        "images": {
            "main": [{
                "path": "images/19396354/main_01.jpg",
                "source_url": "https://oss.example/a.jpg?x-oss-process=style/style350",
            }],
            "detail": [],
        },
    }], ensure_ascii=False), encoding="utf-8")

    rows = load_input_rows(tmp_path)

    assert len(rows) == 1
    assert rows[0].material_name == "水泥"
    assert rows[0].material_category_code == "02"
    assert rows[0].images == [ImageIn(kind="MAIN", rel_path="images/19396354/main_01.jpg", source_url="https://oss.example/a.jpg")]


def test_load_offer_tree_uses_product_name_as_material_name(tmp_path: Path):
    offer_dir = tmp_path / "categories/L1-a/L2-b/offers/19396354"
    (offer_dir / "images").mkdir(parents=True)
    (offer_dir / "images" / "main_01.jpg").write_bytes(b"x")
    (offer_dir / "offer.json").write_text(json.dumps({
        "source": {
            "offer_id": "19396354",
            "offer_url": "https://www.xfs.com/productsku/19396354.html",
        },
        "source_category_path": [{"name_zh": "涂料化工"}, {"name_zh": "水泥"}],
        "product_name_zh": "水泥",
        "listing_title_zh": "洪双竹 PC325/PF325水泥 50kg",
        "gallery": [{"path": "images/main_01.jpg", "source_url": "https://oss.example/main.jpg"}],
        "description_images": [],
    }, ensure_ascii=False), encoding="utf-8")

    rows = load_input_rows(tmp_path)

    assert len(rows) == 1
    assert rows[0].material_name == "水泥"
    assert rows[0].offer_id == "19396354"
    assert rows[0].base_dir == offer_dir
    assert rows[0].images[0] == ImageIn(kind="MAIN", rel_path="images/main_01.jpg", source_url="https://oss.example/main.jpg")


def test_resolve_spu_code_matches_single_material_by_name():
    row = type("Row", (), {
        "spu_code": None,
        "material_category_code": "02",
        "material_name": "水泥",
    })()
    material_index = {
        "水泥": [{"cat_code": "02", "cat_name": "水泥类", "name": "水泥",
                 "spu_code": zsoe_spu_code("02", "水泥")}],
    }

    got, reason = resolve_spu_code(row, material_index)

    assert reason is None
    assert got == zsoe_spu_code("02", "水泥")


def test_resolve_spu_code_refuses_material_absent_from_table():
    row = type("Row", (), {
        "spu_code": None,
        "material_category_code": "02",
        "material_name": "水泥",
    })()

    got, reason = resolve_spu_code(row, {})

    assert got is None
    assert "不在央企材料表" in reason


def test_resolve_spu_code_refuses_ambiguous_name_without_category():
    row = type("Row", (), {
        "spu_code": None,
        "material_category_code": None,
        "material_name": "镀锌钢管",
    })()
    material_index = {
        "镀锌钢管": [
            {"cat_code": "03", "cat_name": "钢材类", "name": "镀锌钢管", "spu_code": "A"},
            {"cat_code": "11", "cat_name": "给排水类", "name": "镀锌钢管", "spu_code": "B"},
        ]
    }

    got, reason = resolve_spu_code(row, material_index)

    assert got is None
    assert "材料名重名" in reason


def test_should_hold_low_res_truth_table():
    # 低于门槛 → hold
    assert _should_hold_low_res(445, 600, force_replace=False) is True
    # 达到门槛 → 不 hold
    assert _should_hold_low_res(600, 600, force_replace=False) is False
    # 低于门槛但在 force_replace 白名单 → 照换,不 hold
    assert _should_hold_low_res(445, 600, force_replace=True) is False


def test_load_decisions_parses_force_replace(tmp_path: Path):
    # force_replace.list 必须被解析进 decisions,否则整条"低清照换"意图静默失效
    (tmp_path / "d.json").write_text(json.dumps({
        "force_replace": {"_说明": "x", "list": ["污泥阀", "带 空格 名"]},
    }, ensure_ascii=False), encoding="utf-8")

    dec = load_decisions(tmp_path / "d.json")

    assert _hard("污泥阀") in dec.force_replace
    assert _hard("带空格名") in dec.force_replace  # _hard 去空格后匹配


def test_load_decisions_missing_force_replace_is_empty(tmp_path: Path):
    (tmp_path / "d.json").write_text(json.dumps({"name_overrides": {}}), encoding="utf-8")
    dec = load_decisions(tmp_path / "d.json")
    assert dec.force_replace == set()
