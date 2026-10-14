from app.db.models.zone import Zone, ZoneCategory, ZoneProduct, ZoneGrant


def test_zone_product_has_composite_fk():
    names = {c.name for c in ZoneProduct.__table__.constraints}
    assert "fk_zone_products_category_same_zone" in names
    assert "uq_zone_products_triplet" in names


def test_zone_category_has_zone_scoped_unique():
    names = {c.name for c in ZoneCategory.__table__.constraints}
    assert "uq_zone_categories_zone_id_id" in names


def test_zone_grant_has_zone_org_unique():
    names = {c.name for c in ZoneGrant.__table__.constraints}
    assert "uq_zone_grants_zone_org" in names


def test_zone_has_unique_code_column():
    assert Zone.__table__.c.code.unique is True


def test_zone_category_kind_column_defaults_to_category():
    from app.db.models.zone import ZONE_CATEGORY_KIND_CATEGORY, ZONE_CATEGORY_KIND_SCENE
    col = ZoneCategory.__table__.c.kind
    assert col.nullable is False
    assert col.server_default.arg == "CATEGORY"
    assert ZONE_CATEGORY_KIND_CATEGORY == "CATEGORY"
    assert ZONE_CATEGORY_KIND_SCENE == "SCENE"
