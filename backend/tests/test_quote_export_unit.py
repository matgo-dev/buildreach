"""报价单模板上下文单测(纯逻辑,不连 DB / 不调 weasyprint)。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from app.schemas.quote import RfqQuoteBuyerPublic
from app.services import quote_export


def _rfq(**kw):
    base = dict(
        rfq_no="RFQ-20260916-0001",
        contact_name="liujj",
        contact_email="buyer@example.com",
        contact_phone="+255700000001",
        requested_delivery_place=None,
        destination_port=None,
        expected_delivery_date=None,
        created_at=datetime(2026, 9, 16, 8, 0),
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _quote(**kw):
    return RfqQuoteBuyerPublic(
        id=1, quote_no="Q-20261012-0003", quoted_at=datetime(2026, 10, 12, 9, 30), **kw
    )


def _ctx(rfq=None, quote=None, buyer_org_name="Lumi Trading Ltd", locale="en"):
    return quote_export._template_context(
        rfq=rfq or _rfq(),
        quote=quote or _quote(),
        buyer_org_name=buyer_org_name,
        image_map={},
        locale=locale,
        now=datetime(2026, 10, 15, 0, 0),
    )


def _html(**kw) -> str:
    return quote_export._jinja_env.get_template("quote.html").render(**_ctx(**kw))


def test_issue_date_is_quoted_at_not_rfq_created_at():
    assert _ctx()["issue_date"] == "2026-10-12"


def test_issue_date_missing_quoted_at_shows_dash_not_rfq_date():
    ctx = _ctx(quote=RfqQuoteBuyerPublic(id=1, quote_no="Q-1"))
    assert ctx["issue_date"] == "—"


def test_platform_header_is_matgo_not_legacy_brand():
    html = _html()
    assert "BuildLink" not in html
    for text in (
        "MATGO",
        "MATMART COMPANY LIMITED",
        "Mikocheni A, Kinondoni, Dar es Salaam, Tanzania",
        "P.O. Box 21077",
        "+255 725 511 111",
    ):
        assert text in html


def test_recipient_company_is_org_name_not_contact_name():
    html = _html()
    assert "Lumi Trading Ltd" in html
    assert html.count("liujj") == 1


def test_recipient_company_empty_does_not_fall_back_to_contact_name():
    html = _html(buyer_org_name="")
    assert html.count("liujj") == 1


def test_format_quantity_strips_trailing_zeros():
    f = quote_export._format_quantity
    assert f(Decimal("1.000")) == "1"
    assert f(Decimal("10.500")) == "10.5"
    assert f(Decimal("0.125")) == "0.125"
    assert f(Decimal("200000.000")) == "200,000"
    assert f(None) == "—"
