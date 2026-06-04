"""搜索精细化专项(Δ7 v0.3 §3.13)。country boost + 白名单两阶段兜底。"""
from __future__ import annotations

from app.services.credit.harvester.public_web_harvester import PublicWebHarvester
from tests._harvest_fakes import PROMPTS_ROOT, FakeLLM, FakeTavily, basic_json, tavily_result


def _h(tavily, llm) -> PublicWebHarvester:
    return PublicWebHarvester(tavily, llm, PROMPTS_ROOT)


async def test_country_parameter_passed_to_tavily():
    tavily = FakeTavily()
    await _h(tavily, FakeLLM(basic_json())).harvest_basic("X", "KH", None)
    assert tavily.calls and all(c["country"] == "cambodia" for c in tavily.calls)


async def test_whitelist_first_call_uses_include_domains():
    tavily = FakeTavily()
    await _h(tavily, FakeLLM(basic_json())).harvest_basic("X", "KH", None)
    assert tavily.calls[0]["include_domains"]  # 白名单非空
    assert "businessregistration.moc.gov.kh" in tavily.calls[0]["include_domains"]


async def test_fallback_call_when_below_threshold():
    # 白名单返回 1 条 < 3 → 触发第二次全网兜底(不带 include_domains)
    tavily = FakeTavily(results=[tavily_result()])
    await _h(tavily, FakeLLM(basic_json())).harvest_basic("X", "KH", None)
    assert len(tavily.calls) == 2
    assert tavily.calls[1]["include_domains"] is None


async def test_no_fallback_when_threshold_met():
    # 白名单返回 3 条 ≥ 阈值 → 不触发兜底,只 1 次调用
    three = [tavily_result(url=f"https://a{i}.kh") for i in range(3)]
    tavily = FakeTavily(results_by_call=[three])
    await _h(tavily, FakeLLM(basic_json())).harvest_basic("X", "KH", None)
    assert len(tavily.calls) == 1


async def test_fallback_results_deduplicated_by_url():
    wl = [tavily_result(url="https://dup.kh")]
    fb = [tavily_result(url="https://dup.kh"), tavily_result(url="https://new.kh")]
    tavily = FakeTavily(results_by_call=[wl, fb])
    r = await _h(tavily, FakeLLM(basic_json())).harvest_basic("X", "KH", None)
    urls = [t["url"] for t in r.tavily_results]
    assert urls.count("https://dup.kh") == 1  # 去重
    assert "https://new.kh" in urls


async def test_country_not_configured_skip_country_param():
    # 非 KH(无 country 映射)→ 不传 country
    tavily = FakeTavily()
    await _h(tavily, FakeLLM(basic_json())).harvest_basic("X", "PK", None)
    assert tavily.calls and all(c["country"] is None for c in tavily.calls)


async def test_no_whitelist_skip_first_stage():
    # 无白名单(PK 无 yaml)→ 直接全网,1 次调用且无 include_domains
    tavily = FakeTavily()
    await _h(tavily, FakeLLM(basic_json())).harvest_basic("X", "PK", None)
    assert len(tavily.calls) == 1
    assert tavily.calls[0]["include_domains"] is None
