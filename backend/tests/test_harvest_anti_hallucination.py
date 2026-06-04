"""反幻觉后处理单测(Δ7 §4.1,v0.3)。无有效证据的字段强制置 null。"""
from __future__ import annotations

from app.services.credit.harvester.public_web_harvester import PublicWebHarvester
from tests._harvest_fakes import PROMPTS_ROOT, FakeLLM, FakeTavily, basic_json, ev, tavily_result


def _h(tavily, llm) -> PublicWebHarvester:
    return PublicWebHarvester(tavily, llm, PROMPTS_ROOT)


async def test_field_without_evidence_forced_null():
    # 有值但 _evidence 完全缺失 → 后处理置 null
    llm = FakeLLM(basic_json(established_date="2010-01-01", _evidence={}))
    r = await _h(FakeTavily(), llm).harvest_basic("A", "KH", None)
    assert r.extracted["established_date"] is None
    assert r.status == "missing"


async def test_short_quote_forced_null():
    # quote < 10 字符 → 无效 → 置 null
    tavily = FakeTavily(results=[tavily_result(content="公司于2010年1月1日成立的相关资料")])
    llm = FakeLLM(basic_json(
        established_date="2010-01-01", _evidence={"established_date": ev("短", 0)}
    ))
    r = await _h(tavily, llm).harvest_basic("A", "KH", None)
    assert r.extracted["established_date"] is None


async def test_valid_quote_kept_and_url_resolved():
    tavily = FakeTavily(results=[
        tavily_result(url="https://kh.x", content="公司于2010年1月1日正式注册成立,资料齐全")
    ])
    llm = FakeLLM(basic_json(
        established_date="2010-01-01",
        _evidence={"established_date": ev("公司于2010年1月1日正式注册成立", 0)},
    ))
    r = await _h(tavily, llm).harvest_basic("A", "KH", None)
    assert r.extracted["established_date"] == "2010-01-01"
    assert r.evidence["established_date"].source_url == "https://kh.x"


async def test_llm_failure_retries_then_failed():
    r = await _h(FakeTavily(), FakeLLM(raise_error=True)).harvest_basic("A", "KH", None)
    assert r.status == "failed"
    assert r.llm_calls == 2  # 1 + retry(1)


async def test_invalid_json_failed():
    r = await _h(FakeTavily(), FakeLLM("这不是JSON")).harvest_basic("A", "KH", None)
    assert r.status == "failed"
    assert r.error and "schema" in r.error
