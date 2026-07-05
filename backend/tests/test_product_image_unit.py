"""上传图片类型判定的纯逻辑单测(不触 DB/HTTP)。

覆盖 resolve_uploaded_image_type 的状态判定分支:
详情图不抢主图、SKU 图不占 SPU 主图、缺主图时主图区图片补位、非法类型回落。
"""
from app.db.models.product_image import ImageType
from app.services.product import resolve_uploaded_image_type


def test_first_spu_carousel_image_becomes_main():
    # 首张 SPU 主图区图片(缺主图)自动补位为 MAIN
    assert resolve_uploaded_image_type("GALLERY", sku_id=None, has_spu_main=False) == ImageType.MAIN


def test_detail_never_becomes_main_even_when_first():
    # 详情图不参与主图指派,即便当前无主图
    assert resolve_uploaded_image_type("DETAIL", sku_id=None, has_spu_main=False) == ImageType.DETAIL


def test_carousel_image_stays_gallery_when_main_exists():
    assert resolve_uploaded_image_type("GALLERY", sku_id=None, has_spu_main=True) == ImageType.GALLERY


def test_sku_image_never_becomes_spu_main():
    # SKU 级图片即便缺 SPU 主图也不补位,避免变体图变成 SPU 封面
    assert resolve_uploaded_image_type("GALLERY", sku_id=42, has_spu_main=False) == ImageType.GALLERY


def test_invalid_type_falls_back_to_gallery():
    assert resolve_uploaded_image_type("BOGUS", sku_id=None, has_spu_main=True) == ImageType.GALLERY
