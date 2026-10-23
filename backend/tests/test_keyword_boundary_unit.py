"""商城搜索「词首」正则纯逻辑单测(不连 DB)。"""
from __future__ import annotations

import re

from app.services.product import keyword_word_boundary_regex as rx


def _hit(keyword: str, text: str) -> bool:
    pattern = rx(keyword)
    assert pattern is not None
    return re.search(pattern, text, re.IGNORECASE) is not None


def test_letter_keyword_must_not_follow_a_letter():
    assert _hit("cement", "Portland Cement 42.5R")
    assert not _hit("cement", "Positive Displacement Pump")
    assert not _hit("cement", "Basalt fiber reinforcement")
    assert not _hit("tee", "Deli Steel Ruler")
    assert _hit("tee", "Brass Tee fitting")
    assert _hit("DN20", "球阀DN20")          # 汉字算分隔
    assert _hit("750V", "450/750V wire")     # 符号算分隔


def test_digit_keyword_must_not_follow_digit_or_decimal():
    assert _hit("304", "SUS304 不锈钢")       # 字母→数字算词首
    assert not _hit("304", "1304 件")
    assert not _hit("304", "1,304 件")
    assert not _hit("20mm", "600*120mm")
    assert not _hit("5mm", "Crystal board 1.5mm")
    assert _hit("20mm", "PE管 20mm")
    assert _hit("4.5", "φ110*4.5*4000mm")
    # 点/逗号前不是数字 → 是分隔符,不是数字的一部分
    assert _hit("20mm", "Size 16mm,20mm,25mm")
    assert _hit("304", "Art.No.304 valve")
    assert _hit("200", "KLC-S N.20005")
    assert _hit("5mm", ".5mm foil")


def test_prefix_still_allowed():
    assert _hit("pipe", "Steel Pipes")       # 只约束开头,pipes 仍命中
    assert _hit("m8x", "Hex Bolt M8x20")


def test_no_boundary_for_cjk_symbol_start_or_short():
    assert rx("水泥") is None
    assert rx("+255") is None
    assert rx("") is None
    assert rx("PE") is None   # <3 字符走不了索引,保持纯子串
    assert rx("m8") is None
    assert rx(" PE ") is None  # 按去空白后的长度判断
    assert rx(" cement") is None  # 前导空白:ILIKE '% cement%' 已是词首,再加正则会误杀 Portland cement
    assert rx("cement ") == "(^|[^A-Za-z])cement "  # 尾部空白照常


def test_regex_specials_are_escaped():
    assert _hit("M8*20", "Hex Bolt M8*20 zinc")
    assert not _hit("M8*20", "Hex Bolt M820 zinc")
    assert _hit("1.5mm", "Crystal board 1.5mm")
    assert not _hit("1.5mm", "Crystal board 105mm")
    assert _hit("A(B)", "part A(B) x")
    assert _hit("C\\D", "path C\\D here")
