"""矿业专区导入脚本纯函数单测:表格解析 / 品名合并 / 规则匹配 / 编码稳定性。不碰 DB。"""
from __future__ import annotations

from pathlib import Path

import openpyxl
import pytest

from app.services.product_code import platform_spu_code
from scripts.import_zone_mining import (
    Rule,
    SourceRow,
    build_spus,
    extract_applicable_model,
    hard,
    load_merge_map,
    load_rules,
    load_source_rows,
    match_rule,
    mining_spu_code,
)


def _write_book(path: Path, sheets: dict[str, list[list]]) -> None:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        for r in rows:
            ws.append(r)
    wb.save(path)


def test_hard_normalizes_fullwidth_and_whitespace():
    assert hard("８φ 绳卡　") == "8φ绳卡"


def test_mining_spu_code_is_platform_neutral_and_stable():
    code = mining_spu_code("绳卡")
    assert code == platform_spu_code("ZMINE", "绳卡")
    assert code.startswith("MG-P") and len(code) == 16
    assert "ZMINE" not in code and "绳卡" not in code


def test_load_source_rows_handles_both_header_variants(tmp_path: Path):
    _write_book(tmp_path / "01_浮选厂.xlsx", {
        "浮选设备与备件": [
            ["标题行"], [],
            ["编号", "环节/类别", "设备、配件及易耗品", "参考型号/规格", "单位", "100吨", "500吨", "a", "b", "c", "d", "是否通用"],
            ["F-01", "备件", "颚式破碎机颚板", "按颚破型号、图号及齿形", "套", 1, 1, None, None, None, None, "否（机型专用）"],
            [None, None, None, None, None],
        ],
        "规模与汇总": [["不导入"]],
    })
    _write_book(tmp_path / "600型与800型.xlsx", {
        "600型10台预算": [
            ["编号", "配件名称", "型号或规格", "单位", "半年参考量"],
            ["新R007", "钢丝绳", "6mm×1000m", "捆", None],
        ],
        "800型10台预算": [["编号", "配件名称"], ["新R007", "钢丝绳"]],
    })
    rows = load_source_rows(tmp_path)
    assert [(r.file_key, r.sheet, r.row_id, r.name) for r in rows] == [
        ("01", "浮选设备与备件", "F-01", "颚式破碎机颚板"),
        ("600", "600型10台预算", "新R007", "钢丝绳"),
    ]
    assert rows[0].section == "备件"
    assert rows[0].spec_text == "按颚破型号、图号及齿形"
    assert rows[0].unit == "套"
    assert rows[0].generic == "否（机型专用）"
    assert rows[1].section == ""  # 600 表没有类别列


def test_load_merge_map_and_blank_spec_is_alias(tmp_path: Path):
    p = tmp_path / "spu_merge.csv"
    p.write_text("原品名,SPU品名,规格\n8φ绳卡,绳卡,φ8\n颚破边护板,颚式破碎机边护板,\n", encoding="utf-8")
    m = load_merge_map(p)
    assert m[hard("8φ绳卡")] == ("绳卡", "φ8")
    assert m[hard("颚破边护板")] == ("颚式破碎机边护板", "")


def test_match_rule_keyword_rules_win_over_sheet_defaults():
    rules = [
        Rule("01", "药剂及钢球", "*", "", "C04", "34.001"),
        Rule("01", "药剂及钢球", "*", "钢球", "C01", "33.001"),
        Rule("01", "*", "劳保", "", "C10", "01"),
    ]
    ball = SourceRow("01", "药剂及钢球", "X-1", "", "研磨钢球", "", "吨", "")
    agent = SourceRow("01", "药剂及钢球", "X-2", "", "捕收剂", "", "kg", "")
    glove = SourceRow("01", "浮选现场配套", "X-3", "劳保", "帆布手套", "", "双", "")
    other = SourceRow("02", "井下设备备件", "X-4", "", "钎杆", "", "根", "")
    assert match_rule(ball, rules).zone_cat == "C01"
    assert match_rule(agent, rules).zone_cat == "C04"
    assert match_rule(glove, rules).zone_cat == "C10"
    assert match_rule(other, rules) is None


def test_load_rules_reads_csv(tmp_path: Path):
    p = tmp_path / "rules.csv"
    p.write_text("file_key,sheet,section,keyword,zone_cat,category_code,note\n01,*,*,,C10,01,x\n", encoding="utf-8")
    rules = load_rules(p)
    assert rules == [Rule("01", "*", "*", "", "C10", "01")]


@pytest.mark.parametrize("text,expected", [
    ("按凿岩机/气腿品牌型号及零件号核样", "凿岩机/气腿品牌型号"),
    ("按斗齿系统、销孔、斗号和机型", "斗齿系统、销孔、斗号和机型"),
    ("示例:玻璃100mL,单只", None),
    ("", None),
])
def test_extract_applicable_model(text, expected):
    assert extract_applicable_model(text) == expected


def _rules_default():
    return [
        Rule("01", "*", "*", "", "C10", "01"),
        Rule("02", "*", "*", "", "C09", "04"),
    ]


def test_build_spus_merges_sizes_into_skus_and_unions_scenes():
    rows = [
        SourceRow("01", "浮选现场配套", "A-1", "耗材", "8φ绳卡", "原文φ8", "个", "限同制式或接口"),
        SourceRow("01", "浮选现场配套", "A-2", "耗材", "15φ绳卡", "原文φ15", "个", "限同制式或接口"),
        SourceRow("02", "井下设备备件", "B-1", "耗材", "8φ绳卡", "原文φ8", "个", "限同制式或接口"),
    ]
    merge = {hard("8φ绳卡"): ("绳卡", "φ8"), hard("15φ绳卡"): ("绳卡", "φ15")}
    rules = [Rule("*", "*", "*", "", "C09", "04")]
    spus = build_spus(rows, merge, rules)
    assert len(spus) == 1
    s = spus[0]
    assert s.name == "绳卡"
    assert s.spu_code == mining_spu_code("绳卡")
    assert s.specs == ["φ8", "φ15"]
    assert s.scenes == ["S01", "S02"]
    assert s.description == "原文φ8"
    assert s.source_ids == ["01:A-1", "01:A-2", "02:B-1"]
    assert s.zone_cat == "C09" and s.category_code == "04"
    assert s.conflicts == []


def test_build_spus_reports_category_conflict():
    rows = [
        SourceRow("01", "浮选现场配套", "A-1", "劳保", "帆布手套", "", "双", ""),
        SourceRow("02", "全矿共用维修工具", "B-9", "工具", "帆布手套", "", "双", ""),
    ]
    spus = build_spus(rows, {}, _rules_default())
    assert len(spus) == 1
    assert spus[0].zone_cat == "C10"      # 第一次命中为准
    assert spus[0].conflicts == ["02:B-9 → C09/04 ≠ C10/01"]


def test_build_spus_unmatched_row_has_no_zone_cat():
    rows = [SourceRow("03", "两法共用", "LAB-1", "器皿", "烧杯", "", "个", "")]
    spus = build_spus(rows, {}, _rules_default())
    assert spus[0].zone_cat is None and spus[0].category_code is None


def test_load_source_rows_skips_non_product_noise_rows(tmp_path: Path):
    """「待核数量」「xx方案」「xx服务」这类占位/服务行不是商品,解析时丢弃。"""
    _write_book(tmp_path / "05_露天.xlsx", {
        "油品及运行耗材": [
            ["编号", "类别", "设备、配件及易耗品", "参考型号/规格", "单位"],
            ["OP-O001", "油品", "柴油机油", "按厂家规格", "桶"],
            ["OP-X001", "3台挖机方案", "5台挖机方案", "", ""],
            ["OP-X002", "待核数量", "待核数量", "", ""],
            ["OP-X003", "救援", "车辆拖救服务", "", "次"],
        ],
    })
    rows = load_source_rows(tmp_path)
    assert [r.name for r in rows] == ["柴油机油"]


def test_match_rule_file_specific_keyword_beats_wildcard_keyword():
    """同为关键词规则时,写了 file_key 的比 * 的优先,不管谁在前(化验室的「pH计」不能被全局「仪/计」抢走)。"""
    rules = [
        Rule("*", "*", "*", "计", "C06", "14"),
        Rule("03", "*", "*", "计", "C11", "35.001"),
    ]
    lab = SourceRow("03", "两法共用", "LAB-1", "仪器", "实验室pH计", "", "台", "")
    site = SourceRow("04", "回收及公辅", "R-1", "", "流量计", "", "台", "")
    assert match_rule(lab, rules).zone_cat == "C11"
    assert match_rule(site, rules).zone_cat == "C06"
