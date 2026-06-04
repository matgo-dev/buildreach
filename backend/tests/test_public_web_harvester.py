"""PublicWebHarvester 字段映射单测(Δ7 v0.3)。mock Tavily + mock LLM。"""
from __future__ import annotations

import json

from app.services.credit.harvester.public_web_harvester import PublicWebHarvester
from tests._harvest_fakes import (
    PROMPTS_ROOT,
    FakeLLM,
    FakeTavily,
    basic_json,
    ev,
    tavily_result,
)


def _harvester(tavily, llm) -> PublicWebHarvester:
    return PublicWebHarvester(tavily, llm, PROMPTS_ROOT)


async def test_harvest_basic_maps_fields_and_resolves_source_url():
    content = "Kampot Cement 成立于2008年4月15日,注册资本 USD 50,000,000 已实缴"
    tavily = FakeTavily(results=[tavily_result(url="https://moc.gov.kh/x", content=content)])
    llm = FakeLLM(basic_json(
        established_date="2008-04-15",
        registered_capital="USD 50,000,000",
        _evidence={
            "established_date": ev("成立于2008年4月15日", 0),
            "registered_capital": ev("注册资本 USD 50,000,000 已实缴", 0),
        },
        confidence="high",
    ))
    r = await _harvester(tavily, llm).harvest_basic("Kampot Cement", "KH", "12345")

    assert r.status == "partial"  # 8 字段中 2 个有值
    assert r.data_source == "public"
    assert r.extracted["established_date"] == "2008-04-15"
    assert r.extracted["registered_capital"] == "USD 50,000,000"
    assert r.extracted["business_scope"] is None
    assert r.confidence == "high"
    # v0.3:source_index 反查得到 source_url
    assert r.evidence["established_date"].source_index == 0
    assert r.evidence["established_date"].source_url == "https://moc.gov.kh/x"
    assert r.queries and "Kampot Cement" in r.queries[0]


async def test_harvest_basic_all_null_missing():
    h = _harvester(FakeTavily(), FakeLLM(basic_json()))
    r = await h.harvest_basic("ACME", "KH", None)
    assert r.status == "missing"
    assert r.data_source == "missing"


async def test_harvest_tavily_empty_missing_no_llm():
    # 两阶段都返回空 → 无结果 → missing(无 error),不调 LLM
    llm = FakeLLM(basic_json())
    h = _harvester(FakeTavily(results=[]), llm)
    r = await h.harvest_basic("ACME", "KH", None)
    assert r.status == "missing"
    assert r.llm_calls == 0
    assert llm.calls == 0


async def test_harvest_qualifications_returns_list():
    content = "公司已通过 ISO 9001:2015 质量管理体系认证"
    tavily = FakeTavily(results=[tavily_result(content=content)])
    qual = json.dumps({
        "has_iso_9001": True, "has_iso_14001": None, "has_iso_45001": None,
        "has_isc_certification": None, "other_certifications": [],
        "_evidence": {"has_iso_9001": {"quote": "公司已通过 ISO 9001:2015 质量管理体系认证", "source_index": 0}},
        "_confidence": "medium",
    })
    out = await _harvester(tavily, FakeLLM(qual)).harvest_qualifications("ACME", "KH", None)
    assert isinstance(out, list) and len(out) == 1
    assert out[0].extracted["has_iso_9001"] is True
    assert out[0].data_source == "public"


async def test_harvest_legal_media_source():
    content = "媒体报道该公司偶有合同纠纷负面新闻见诸报端"
    tavily = FakeTavily(results=[tavily_result(content=content)])
    legal = json.dumps({
        "litigation_count": None, "defaulter_unresolved_count": None,
        "defaulter_resolved_count": None, "negative_news_level": "occasional",
        "_evidence": {"negative_news_level": {"quote": "媒体报道该公司偶有合同纠纷负面新闻", "source_index": 0}},
        "_confidence": "medium",
    })
    r = await _harvester(tavily, FakeLLM(legal)).harvest_legal("ACME", "KH", None)
    assert r.status == "partial"
    assert r.data_source == "media"
    assert r.extracted["negative_news_level"] == "occasional"
