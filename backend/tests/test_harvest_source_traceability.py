"""源字段追溯专项(Δ7 v0.3 §3.13)。source_index 校验 + URL 反查 + fuzzy + legacy 兼容。"""
from __future__ import annotations

import json

from app.services.credit.harvester.harvest_task import _raw
from app.services.credit.harvester.legacy_compat import get_evidence_map, normalize_field_evidence
from app.services.credit.harvester.public_web_harvester import PublicWebHarvester
from tests._harvest_fakes import PROMPTS_ROOT, FakeLLM, FakeTavily, basic_json, ev, tavily_result


def _h(tavily, llm) -> PublicWebHarvester:
    return PublicWebHarvester(tavily, llm, PROMPTS_ROOT)


async def test_valid_source_index_resolves_url():
    tavily = FakeTavily(results=[
        tavily_result(url="https://a.kh", content="无关内容"),
        tavily_result(url="https://moc.gov.kh", content="公司成立于2008年4月15日,注册地金边"),
    ])
    llm = FakeLLM(basic_json(
        established_date="2008-04-15",
        _evidence={"established_date": ev("公司成立于2008年4月15日", 1)},
    ))
    r = await _h(tavily, llm).harvest_basic("X", "KH", None)
    assert r.extracted["established_date"] == "2008-04-15"
    assert r.evidence["established_date"].source_index == 1
    assert r.evidence["established_date"].source_url == "https://moc.gov.kh"


async def test_out_of_range_source_index_nulls_field():
    tavily = FakeTavily(results=[tavily_result(content="公司成立于2008年的资料记录在此处")])
    llm = FakeLLM(basic_json(
        established_date="2008-01-01",
        _evidence={"established_date": ev("公司成立于2008年的资料", 99)},  # 越界
    ))
    r = await _h(tavily, llm).harvest_basic("X", "KH", None)
    assert r.extracted["established_date"] is None


async def test_quote_too_short_nulls_field():
    tavily = FakeTavily(results=[tavily_result(content="公司成立于2008年的详细资料")])
    llm = FakeLLM(basic_json(
        established_date="2008-01-01", _evidence={"established_date": ev("短", 0)}
    ))
    r = await _h(tavily, llm).harvest_basic("X", "KH", None)
    assert r.extracted["established_date"] is None


async def test_quote_content_mismatch_nulls_field():
    # quote 与 source_index 指向的 content 完全不相关 → fuzzy 低 → null
    tavily = FakeTavily(results=[tavily_result(content="完全无关的内容文本 ABCDEFG XYZ")])
    llm = FakeLLM(basic_json(
        established_date="2008-01-01",
        _evidence={"established_date": ev("公司成立于2008年4月15日整", 0)},
    ))
    r = await _h(tavily, llm).harvest_basic("X", "KH", None)
    assert r.extracted["established_date"] is None


async def test_llm_outputs_url_not_index_field_nulled():
    # LLM 给 source_url 但没 source_index → Schema 只取 quote/source_index;index 缺失 → null
    llm_json = json.dumps({
        "established_date": "2008-01-01", "registered_capital": None, "business_scope": None,
        "legal_representative": None, "shareholders": None, "status_text": None,
        "address": None, "website": None,
        "_evidence": {"established_date": {
            "quote": "公司成立于2008年4月15日整", "source_url": "https://evil.com",
        }},
        "_confidence": "low",
    })
    tavily = FakeTavily(results=[tavily_result(content="公司成立于2008年4月15日整 的官方记录")])
    r = await _h(tavily, FakeLLM(llm_json)).harvest_basic("X", "KH", None)
    assert r.extracted["established_date"] is None  # source_index 缺失 → 校验不过


async def test_evidence_serialization_preserves_source_url():
    tavily = FakeTavily(results=[
        tavily_result(url="https://moc.gov.kh", content="公司成立于2008年4月15日的官方记录")
    ])
    llm = FakeLLM(basic_json(
        established_date="2008-04-15",
        _evidence={"established_date": ev("公司成立于2008年4月15日", 0)},
    ))
    r = await _h(tavily, llm).harvest_basic("X", "KH", None)
    raw = _raw(r, run_id=1)
    assert raw["evidence"]["established_date"]["source_url"] == "https://moc.gov.kh"
    assert raw["evidence"]["established_date"]["source_index"] == 0
    # JSONB round-trip 不丢字段
    restored = json.loads(json.dumps(raw))
    assert restored["evidence"]["established_date"]["quote"]
    assert restored["tavily_results"][0]["index"] == 0


def test_legacy_v02_evidence_format_still_readable():
    # v0.2 旧格式:evidence 为字符串
    v02 = {"evidence": {"established_date": "成立于2008年的记录"}}
    m = get_evidence_map(v02)
    assert m["established_date"]["quote"] == "成立于2008年的记录"
    assert m["established_date"]["source_url"] is None
    # v0.3 新格式:evidence 为对象
    v03 = {"evidence": {"x": {"quote": "q", "source_index": 0, "source_url": "https://u"}}}
    assert get_evidence_map(v03)["x"]["source_url"] == "https://u"
    # 单字段归一化
    assert normalize_field_evidence(None)["quote"] is None
