import json
from pathlib import Path

import pytest

from scripts.import_zone_soe_images_matches import (
    ImageIn,
    LEDGER_PATH,
    MatchIn,
    ZONE_CODE,
    _hard,
    _raw_url,
    _resolve_ledger_path,
    _run_crawled_at,
    _should_hold_low_res,
    load_decisions,
    load_input_rows,
    load_zone_inputs,
    resolve_spu_code,
    should_force_replace,
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


def test_load_matches_json_manual_upload_shape(tmp_path: Path):
    # 人工补图批次:platform_code 给 SPU 身份、无 offer_id、无 matched_category_path
    (tmp_path / "images" / "MG-P034BCC408609").mkdir(parents=True)
    (tmp_path / "images" / "MG-P034BCC408609" / "main_01.png").write_bytes(b"x")
    (tmp_path / "matches.json").write_text(json.dumps([{
        "platform_code": "MG-P034BCC408609",
        "material_name": "Plascon耐碱底漆",
        "material_category_code": "07",
        "material_category_name": "油漆涂料",
        "source": "manual_upload",
        "images": {"main": ["images/MG-P034BCC408609/main_01.png"], "detail": []},
    }], ensure_ascii=False), encoding="utf-8")

    rows = load_input_rows(tmp_path)

    assert len(rows) == 1
    assert rows[0].spu_code == "MG-P034BCC408609"
    assert rows[0].source == "manual_upload"
    assert rows[0].offer_id == "manual_upload"  # 无 offer 时用 source 兜底,不能留空
    assert rows[0].matched_category_path == []


def test_load_matches_json_rejects_row_without_offer_id_or_source(tmp_path: Path):
    (tmp_path / "matches.json").write_text(json.dumps([{
        "material_name": "水泥", "images": {"main": []},
    }], ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="offer_id/source"):
        load_input_rows(tmp_path)


def test_run_crawled_at_falls_back_to_dir_name(tmp_path: Path):
    # 人工批次没有 run.json,台账仍须留下批次标识
    batch = tmp_path / "手动补图_0727_41条"
    batch.mkdir()
    assert _run_crawled_at(batch) == "手动补图_0727_41条"


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


def test_resolve_spu_code_trusts_platform_code_when_name_agrees():
    row = type("Row", (), {
        "spu_code": zsoe_spu_code("02", "水泥"),
        "material_category_code": "02",
        "material_name": "水泥",
    })()
    material_index = {"水泥": [{"cat_code": "02", "cat_name": "水泥类", "name": "水泥",
                              "spu_code": zsoe_spu_code("02", "水泥")}]}

    got, reason = resolve_spu_code(row, material_index)

    assert reason is None
    assert got == zsoe_spu_code("02", "水泥")


def test_resolve_spu_code_refuses_platform_code_conflicting_with_name():
    # 数据包串行:spu_code 指 A、材料名唯一命中 B → 必须拒绝,否则图挂到错商品上
    row = type("Row", (), {
        "spu_code": zsoe_spu_code("02", "水泥"),
        "material_category_code": "01",
        "material_name": "钢筋",
    })()
    material_index = {"钢筋": [{"cat_code": "01", "cat_name": "钢筋类", "name": "钢筋",
                              "spu_code": zsoe_spu_code("01", "钢筋")}]}

    got, reason = resolve_spu_code(row, material_index)

    assert got is None
    assert "spu_code 与材料名不符" in reason


def test_resolve_spu_code_keeps_platform_code_when_name_unresolvable():
    # 名字定位不了(不在表/重名消不掉)时不推翻 spu_code,仍按 spu_code 走
    row = type("Row", (), {
        "spu_code": "MG-PXXXX", "material_category_code": None, "material_name": "表外材料",
    })()

    got, reason = resolve_spu_code(row, {})

    assert reason is None
    assert got == "MG-PXXXX"


def test_should_force_replace_manual_upload_bypasses_low_res_gate():
    manual = type("Row", (), {"source": "manual_upload", "material_name": "Plascon铝漆"})()
    crawled = type("Row", (), {"source": "", "material_name": "Plascon铝漆"})()

    assert should_force_replace(manual, set()) is True
    assert should_force_replace(crawled, set()) is False
    assert should_force_replace(crawled, {_hard("Plascon铝漆")}) is True


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


# ----------------------------- 非央企专区复用(矿业) -----------------------------

def test_load_zone_inputs_skips_soe_table_and_decisions_for_other_zone():
    # 矿业里 安全帽/雨衣/对讲机 与央企重名但 spu_code 不同;拿央企表校验会误判「spu_code 与材料名不符」。
    material_index, decisions = load_zone_inputs("mining")
    assert material_index == {}
    assert decisions.drops == set() and decisions.name_overrides == {}
    row = MatchIn(
        material_name="安全帽", material_category_code=None, material_category_name=None,
        spu_code="MG-PE3D6EF60742A", offer_id="manual_upload", offer_url=None, listing_title=None,
        matched_category_path=[], images=[], base_dir=Path("."), source="manual_upload",
    )
    got, reason = resolve_spu_code(row, material_index, decisions.name_overrides)
    assert (got, reason) == ("MG-PE3D6EF60742A", None)


def test_resolve_ledger_path_is_per_zone(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ZONE_SOE_LEDGER_PATH", raising=False)
    assert _resolve_ledger_path(None, ZONE_CODE) == LEDGER_PATH
    assert _resolve_ledger_path(None, "mining") == LEDGER_PATH.with_name("mining_image_refresh_ledger.csv")
    # CLI 指定优先于一切;env 只对央企专区生效,别的专区不能被 env 带进央企台账。
    assert _resolve_ledger_path(Path("/ledger/x.csv"), "mining") == Path("/ledger/x.csv")
    monkeypatch.setenv("ZONE_SOE_LEDGER_PATH", "/ledger/soe.csv")
    assert _resolve_ledger_path(None, ZONE_CODE) == Path("/ledger/soe.csv")
    assert _resolve_ledger_path(None, "mining") == LEDGER_PATH.with_name("mining_image_refresh_ledger.csv")
