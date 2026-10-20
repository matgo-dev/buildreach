"""专区开关变更计算(纯逻辑):只记录与现值不同的字段,None 表示不改。"""
from __future__ import annotations

from app.db.models.zone import Zone
from app.services.zone_grant import zone_setting_changes


def _zone(status: str = "ACTIVE", is_public: bool = True) -> Zone:
    return Zone(code="Z", name_zh="专区", status=status, is_public=is_public)


def test_none_fields_are_not_changed():
    assert zone_setting_changes(_zone(), None, None) == {}


def test_same_value_is_not_a_change():
    assert zone_setting_changes(_zone("ACTIVE", True), "ACTIVE", True) == {}


def test_status_change_records_from_to():
    assert zone_setting_changes(_zone("ACTIVE"), "INACTIVE", None) == {
        "status": {"from": "ACTIVE", "to": "INACTIVE"}
    }


def test_both_fields_change():
    assert zone_setting_changes(_zone("INACTIVE", False), "ACTIVE", True) == {
        "status": {"from": "INACTIVE", "to": "ACTIVE"},
        "is_public": {"from": False, "to": True},
    }
