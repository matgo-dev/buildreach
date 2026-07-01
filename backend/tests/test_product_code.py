from app.services.product_code import xfs_product_code, xfs_sku_code


def test_xfs_codes_are_platform_codes_without_raw_values():
    spu_code = xfs_product_code("3014838")
    sku_code = xfs_sku_code("12211747")

    assert spu_code.startswith("MG-P")
    assert sku_code.startswith("MG-S")
    assert len(spu_code) == 16
    assert len(sku_code) == 16
    assert "3014838" not in spu_code
    assert "12211747" not in sku_code


def test_xfs_codes_are_stable_and_source_sensitive():
    assert xfs_product_code("3014838") == xfs_product_code("3014838")
    assert xfs_sku_code("12211747") == xfs_sku_code("12211747")
    assert xfs_product_code("3014838") != xfs_sku_code("3014838")
