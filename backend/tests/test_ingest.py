"""商品导入脚本测试(对齐工单 Phase 7)。

同步 session + SAVEPOINT 隔离,参照 test_import_categories.py。
使用 docs/prompts/商品导入/run_20260612_test01 作为测试数据。
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.base import Base
from app.db import models as _models  # noqa: F401 — 让 Alembic 能看到所有模型
from app.db.models import (
    Category,
    IngestRun,
    IngestRunStatus,
    Product,
    ProductAttr,
    ProductImage,
    ProductStatus,
)
from app.db.models.product_image import ImageType
from app.db.url import prepare_sync_url

# 导入脚本函数
from scripts.import_products import (
    CategoryNode,
    OfferFile,
    ValidationResult,
    build_category_tree,
    build_leaf_lookup,
    build_name_lookup,
    close_run,
    flatten_tree,
    import_categories,
    import_offer,
    open_run,
    read_categories_raw,
    read_run_json,
    scan_offers,
    validate_batch,
    write_audit_sync,
    _extract_leaf_name,
    _name_to_slug,
    _strip_level_prefix,
)


TEST_DSN = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://liujingjing@localhost:5433/buildlink_ea_test",
)
SYNC_DSN = prepare_sync_url(TEST_DSN)

# 测试数据目录
TEST_BATCH_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "docs" / "prompts" / "商品导入" / "run_20260612_test01"
)


# ---------- fixture ----------


@pytest.fixture
def sync_db():
    """同步 session,SAVEPOINT 隔离。"""
    from sqlalchemy import event

    engine = create_engine(SYNC_DSN, poolclass=None)
    conn = engine.connect()
    txn = conn.begin()
    # 清空相关表
    conn.execute(text(
        "TRUNCATE ingest_runs, product_images, product_attrs, products, "
        "categories, audit_logs RESTART IDENTITY CASCADE"
    ))
    conn.begin_nested()
    session = Session(bind=conn)

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, transaction):
        if transaction.nested and not transaction._parent.nested:
            sess.begin_nested()

    yield session

    session.close()
    txn.rollback()
    conn.close()
    engine.dispose()


@pytest.fixture
def cat_tree():
    """从测试数据构建分类树。"""
    raw = read_categories_raw(TEST_BATCH_DIR)
    return build_category_tree(raw)


@pytest.fixture
def run_meta():
    return read_run_json(TEST_BATCH_DIR)


@pytest.fixture
def offers():
    return scan_offers(TEST_BATCH_DIR)


# ---------- Phase 3: reader + validation ----------


class TestReader:
    def test_read_run_json(self, run_meta):
        assert run_meta.source == "alibaba"
        assert run_meta.operator == "九云"

    def test_build_category_tree(self, cat_tree):
        flat = flatten_tree(cat_tree)
        assert len(flat) == 7
        # L4 存在
        l4 = [n for n in flat if n.level == 4]
        assert len(l4) == 1
        assert l4[0].name_en == "SPC Flooring"

    def test_leaf_lookup(self, cat_tree):
        lookup = build_leaf_lookup(cat_tree)
        # 叶子 = 无子节点:SPC Flooring(L4) 和 Kitchen Faucets(L3)
        assert len(lookup) == 2
        assert "SPC Flooring" in lookup
        assert "Kitchen Faucets" in lookup
        # 非叶子不在
        assert "Flooring" not in lookup

    def test_scan_offers(self, offers):
        assert len(offers) == 4
        ids = {o.offer_id for o in offers}
        assert "1601220380842" in ids
        assert "TEST00000002" in ids

    def test_extract_leaf_name(self):
        path = [{"name_en": "A", "name_zh": "甲"}, {"name_en": "B", "name_zh": "乙"}]
        assert _extract_leaf_name(path) == "B"
        assert _extract_leaf_name([]) is None

    def test_name_to_slug(self):
        assert _name_to_slug("SPC Flooring") == "spc-flooring"
        assert _name_to_slug("Home & Garden") == "home-garden"
        assert _name_to_slug("Kitchen Faucets") == "kitchen-faucets"

    def test_strip_level_prefix(self):
        assert _strip_level_prefix("L1-construction-real-estate__建筑及房地产") == "construction-real-estate"
        assert _strip_level_prefix("L4-spc-flooring__SPC地板") == "spc-flooring"


class TestValidation:
    def test_valid_offers_pass(self, cat_tree, offers, run_meta):
        vr = validate_batch(TEST_BATCH_DIR, run_meta, cat_tree, offers)
        # 2 个通过,2 个失败
        assert len(vr.offer_errors) == 2
        valid = [o for o in offers if o.offer_id not in vr.offer_errors]
        assert len(valid) == 2

    def test_category_mismatch_detected(self, cat_tree, offers, run_meta):
        vr = validate_batch(TEST_BATCH_DIR, run_meta, cat_tree, offers)
        # TEST00000002: Bamboo Flooring 不在分类树
        assert "TEST00000002" in vr.offer_errors
        errs = vr.offer_errors["TEST00000002"]
        assert any("Bamboo Flooring" in e for e in errs)

    def test_offer_id_mismatch_detected(self, cat_tree, offers, run_meta):
        vr = validate_batch(TEST_BATCH_DIR, run_meta, cat_tree, offers)
        # TEST00000004: 目录名 vs JSON offer_id 不一致
        assert "TEST00000004" in vr.offer_errors
        errs = vr.offer_errors["TEST00000004"]
        assert any("不一致" in e for e in errs)

    def test_cross_validate_directory_warning(self, cat_tree, offers, run_meta):
        vr = validate_batch(TEST_BATCH_DIR, run_meta, cat_tree, offers)
        # TEST00000002 目录 slug (spc-flooring) 和 source_category_path leaf (bamboo-flooring) 不一致
        assert any("spc-flooring" in w and "bamboo-flooring" in w for w in vr.warnings)

    def test_empty_attribute_values_warn_but_do_not_block_offer(self, tmp_path, run_meta):
        batch_dir = tmp_path / "batch"
        shutil.copytree(TEST_BATCH_DIR, batch_dir)
        offer_json = next(batch_dir.rglob("offers/1601220380842/offer.json"))
        data = json.loads(offer_json.read_text(encoding="utf-8"))
        data["attributes"][0]["values"] = []
        offer_json.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        cat_tree = build_category_tree(read_categories_raw(batch_dir))
        offers = scan_offers(batch_dir)
        vr = validate_batch(batch_dir, run_meta, cat_tree, offers)

        assert "1601220380842" not in vr.offer_errors
        assert any(
            "[1601220380842]" in warning
            and "attributes[0]" in warning
            and "values 为空" in warning
            for warning in vr.warnings
        )


# ---------- Phase 4: category import ----------


class TestCategoryImport:
    def test_import_creates_all_levels(self, sync_db, cat_tree):
        slug_to_code = import_categories(sync_db, cat_tree)
        sync_db.flush()

        cats = sync_db.execute(select(Category)).scalars().all()
        assert len(cats) == 7

        # L4 存在
        l4 = [c for c in cats if c.level == 4]
        assert len(l4) == 1
        assert l4[0].name_en == "SPC Flooring"

        # parent_code 链完整
        spc = l4[0]
        parent = sync_db.execute(
            select(Category).where(Category.code == spc.parent_code)
        ).scalar_one()
        assert parent.name_en == "Plastic Flooring"
        assert parent.level == 3

    def test_import_idempotent(self, sync_db, cat_tree):
        """重跑不翻倍。"""
        import_categories(sync_db, cat_tree)
        sync_db.flush()
        count1 = sync_db.execute(select(func.count()).select_from(Category)).scalar()

        import_categories(sync_db, cat_tree)
        sync_db.flush()
        count2 = sync_db.execute(select(func.count()).select_from(Category)).scalar()

        assert count1 == count2 == 7

    def test_slug_to_code_mapping(self, sync_db, cat_tree):
        slug_to_code = import_categories(sync_db, cat_tree)
        assert "SPC Flooring" in slug_to_code
        assert "Kitchen Faucets" in slug_to_code
        # code 不为空
        for name, code in slug_to_code.items():
            assert code, f"{name} 的 code 为空"

    def test_leaf_is_no_children(self, sync_db, cat_tree):
        """叶子判定 = DB 中无子节点。"""
        import_categories(sync_db, cat_tree)
        sync_db.flush()

        # SPC Flooring(L4) 是叶子——无子节点
        spc = sync_db.execute(
            select(Category).where(Category.name_en == "SPC Flooring")
        ).scalar_one()
        child = sync_db.execute(
            select(Category).where(Category.parent_code == spc.code)
        ).scalar_one_or_none()
        assert child is None  # 无子节点 = 叶子

        # Flooring(L2) 不是叶子——有子节点
        flooring = sync_db.execute(
            select(Category).where(Category.name_en == "Flooring")
        ).scalar_one()
        child = sync_db.execute(
            select(Category).where(Category.parent_code == flooring.code)
        ).scalar_one_or_none()
        assert child is not None  # 有子节点 = 非叶子


# ---------- Phase 5: product import ----------


class TestProductImport:
    @pytest.fixture
    def prepared_db(self, sync_db, cat_tree, run_meta):
        """导入分类 + 开 run,返回 (db, slug_to_code, run)。"""
        slug_to_code = import_categories(sync_db, cat_tree)
        sync_db.flush()
        run = open_run(
            sync_db,
            run_key="test_run",
            source=run_meta.source,
            operator=run_meta.operator,
            raw_path=str(TEST_BATCH_DIR),
            crawled_at=None,
        )
        sync_db.flush()
        return sync_db, slug_to_code, run

    def _get_valid_offer(self, cat_tree, offers, run_meta) -> OfferFile:
        """拿第一个校验通过的 offer(1601220380842)。"""
        vr = validate_batch(TEST_BATCH_DIR, run_meta, cat_tree, offers)
        valid = [o for o in offers if o.offer_id not in vr.offer_errors]
        return valid[0]

    def test_import_creates_product(self, prepared_db, cat_tree, offers, run_meta):
        db, slug_to_code, run = prepared_db
        offer = self._get_valid_offer(cat_tree, offers, run_meta)
        static_root = Path("/tmp/test_ingest_static")
        static_root.mkdir(exist_ok=True)

        import_offer(
            db, offer,
            slug_to_code=slug_to_code,
            leaf_lookup=build_leaf_lookup(cat_tree),
            run=run, run_meta=run_meta, static_root=static_root,
        )
        db.flush()

        product = db.execute(
            select(Product).where(Product.spu_code == f"P-{offer.offer_id}")
        ).scalar_one()
        assert product.name_en == "SPC Flooring"
        assert product.source == "alibaba"
        assert product.status == ProductStatus.DRAFT
        assert product.last_ingest_run_id == run.id

    def test_import_description_falls_back_to_listing_title(
        self, prepared_db, cat_tree, offers, run_meta,
    ):
        db, slug_to_code, run = prepared_db
        offer = self._get_valid_offer(cat_tree, offers, run_meta)
        assert offer.data is not None
        offer.data["description_en"] = ""
        offer.data["description_zh"] = ""
        offer.data["listing_title_en"] = "Fallback listing title EN"
        offer.data["listing_title_zh"] = "兜底列表标题中文"
        static_root = Path("/tmp/test_ingest_static")
        static_root.mkdir(exist_ok=True)

        import_offer(
            db, offer,
            slug_to_code=slug_to_code,
            leaf_lookup=build_leaf_lookup(cat_tree),
            run=run, run_meta=run_meta, static_root=static_root,
        )
        db.flush()

        product = db.execute(
            select(Product).where(Product.spu_code == f"P-{offer.offer_id}")
        ).scalar_one()
        assert product.description_en == "Fallback listing title EN"
        assert product.description_zh == "兜底列表标题中文"

    def test_attrs_multi_value_n_rows(self, prepared_db, cat_tree, offers, run_meta):
        """values 有几个插几行——Feature 有 3 个值应该 3 行。"""
        db, slug_to_code, run = prepared_db
        offer = self._get_valid_offer(cat_tree, offers, run_meta)
        static_root = Path("/tmp/test_ingest_static")
        static_root.mkdir(exist_ok=True)

        import_offer(
            db, offer,
            slug_to_code=slug_to_code,
            leaf_lookup=build_leaf_lookup(cat_tree),
            run=run, run_meta=run_meta, static_root=static_root,
        )
        db.flush()

        product = db.execute(
            select(Product).where(Product.spu_code == f"P-{offer.offer_id}")
        ).scalar_one()

        feature_attrs = db.execute(
            select(ProductAttr).where(
                ProductAttr.product_id == product.id,
                ProductAttr.attr_key_en == "Feature",
            )
        ).scalars().all()
        # Feature 有 Waterproof, Anti-slip, Wear-resistant = 3 行
        assert len(feature_attrs) == 3
        values = {a.attr_value_en for a in feature_attrs}
        assert "Waterproof" in values
        assert "Anti-slip" in values

    def test_attrs_bilingual(self, prepared_db, cat_tree, offers, run_meta):
        """属性双语:attr_key_zh / attr_value_zh 正确落库。"""
        db, slug_to_code, run = prepared_db
        offer = self._get_valid_offer(cat_tree, offers, run_meta)
        static_root = Path("/tmp/test_ingest_static")
        static_root.mkdir(exist_ok=True)

        import_offer(
            db, offer,
            slug_to_code=slug_to_code,
            leaf_lookup=build_leaf_lookup(cat_tree),
            run=run, run_meta=run_meta, static_root=static_root,
        )
        db.flush()

        product = db.execute(
            select(Product).where(Product.spu_code == f"P-{offer.offer_id}")
        ).scalar_one()

        material = db.execute(
            select(ProductAttr).where(
                ProductAttr.product_id == product.id,
                ProductAttr.attr_key_en == "Material",
            )
        ).scalar_one()
        assert material.attr_key_zh == "材质"
        assert material.attr_value_en == "PVC"
        assert material.attr_value_zh == "PVC"
        assert material.attr_group == "Key attributes"

    def test_color_swatch_image(self, prepared_db, cat_tree, offers, run_meta):
        """色板图:label + swatch_image 同时有 → 属性 text + 图片 spec_value 绑定。"""
        db, slug_to_code, run = prepared_db
        offer = self._get_valid_offer(cat_tree, offers, run_meta)
        static_root = Path("/tmp/test_ingest_static")
        static_root.mkdir(exist_ok=True)

        import_offer(
            db, offer,
            slug_to_code=slug_to_code,
            leaf_lookup=build_leaf_lookup(cat_tree),
            run=run, run_meta=run_meta, static_root=static_root,
        )
        db.flush()

        product = db.execute(
            select(Product).where(Product.spu_code == f"P-{offer.offer_id}")
        ).scalar_one()

        # Oak 颜色属性存在
        oak_attr = db.execute(
            select(ProductAttr).where(
                ProductAttr.product_id == product.id,
                ProductAttr.attr_key_en == "Color",
                ProductAttr.attr_value_en == "Oak",
            )
        ).scalar_one()
        assert oak_attr.value_type == "text"
        assert oak_attr.attr_value_zh == "橡木"

        # 色板图存在且绑定 spec_value
        swatch_imgs = db.execute(
            select(ProductImage).where(
                ProductImage.product_id == product.id,
                ProductImage.spec_value.isnot(None),
            )
        ).scalars().all()
        spec_values = {img.spec_value for img in swatch_imgs}
        assert "颜色:Oak" in spec_values
        assert "颜色:Walnut" in spec_values

    def test_images_main_gallery_detail(self, prepared_db, cat_tree, offers, run_meta):
        """图片类型:首张 MAIN,其余 GALLERY;description_images → DETAIL。"""
        db, slug_to_code, run = prepared_db
        offer = self._get_valid_offer(cat_tree, offers, run_meta)
        static_root = Path("/tmp/test_ingest_static")
        static_root.mkdir(exist_ok=True)

        import_offer(
            db, offer,
            slug_to_code=slug_to_code,
            leaf_lookup=build_leaf_lookup(cat_tree),
            run=run, run_meta=run_meta, static_root=static_root,
        )
        db.flush()

        product = db.execute(
            select(Product).where(Product.spu_code == f"P-{offer.offer_id}")
        ).scalar_one()

        images = db.execute(
            select(ProductImage).where(
                ProductImage.product_id == product.id,
                ProductImage.spec_value.is_(None),
            ).order_by(ProductImage.sort_order)
        ).scalars().all()

        main_imgs = [i for i in images if i.image_type == ImageType.MAIN]
        gallery_imgs = [i for i in images if i.image_type == ImageType.GALLERY]
        detail_imgs = [i for i in images if i.image_type == ImageType.DETAIL]

        assert len(main_imgs) == 1  # 首张 MAIN
        assert len(gallery_imgs) == 1  # 第二张 GALLERY
        assert len(detail_imgs) == 1  # description_images

    def test_idempotent_no_duplicate(self, prepared_db, cat_tree, offers, run_meta):
        """重导同一 offer,行数不翻倍(子行先清后插)。"""
        db, slug_to_code, run = prepared_db
        offer = self._get_valid_offer(cat_tree, offers, run_meta)
        static_root = Path("/tmp/test_ingest_static")
        static_root.mkdir(exist_ok=True)

        # 第一次
        import_offer(
            db, offer,
            slug_to_code=slug_to_code,
            leaf_lookup=build_leaf_lookup(cat_tree),
            run=run, run_meta=run_meta, static_root=static_root,
        )
        db.flush()

        product = db.execute(
            select(Product).where(Product.spu_code == f"P-{offer.offer_id}")
        ).scalar_one()
        attrs1 = db.execute(
            select(func.count()).where(ProductAttr.product_id == product.id)
        ).scalar()
        imgs1 = db.execute(
            select(func.count()).where(ProductImage.product_id == product.id)
        ).scalar()

        # 第二次
        import_offer(
            db, offer,
            slug_to_code=slug_to_code,
            leaf_lookup=build_leaf_lookup(cat_tree),
            run=run, run_meta=run_meta, static_root=static_root,
        )
        db.flush()

        attrs2 = db.execute(
            select(func.count()).where(ProductAttr.product_id == product.id)
        ).scalar()
        imgs2 = db.execute(
            select(func.count()).where(ProductImage.product_id == product.id)
        ).scalar()

        assert attrs1 == attrs2
        assert imgs1 == imgs2

    def test_selling_points_from_feature(self, prepared_db, cat_tree, offers, run_meta):
        """selling_points 从 Feature 属性提取。"""
        db, slug_to_code, run = prepared_db
        offer = self._get_valid_offer(cat_tree, offers, run_meta)
        static_root = Path("/tmp/test_ingest_static")
        static_root.mkdir(exist_ok=True)

        import_offer(
            db, offer,
            slug_to_code=slug_to_code,
            leaf_lookup=build_leaf_lookup(cat_tree),
            run=run, run_meta=run_meta, static_root=static_root,
        )
        db.flush()

        product = db.execute(
            select(Product).where(Product.spu_code == f"P-{offer.offer_id}")
        ).scalar_one()
        assert "Waterproof" in (product.selling_points_en or "")
        assert "防水" in (product.selling_points_zh or "")


# ---------- Phase 6: publish exemption ----------


class TestPublishExemption:
    """上架豁免:非 MANUAL 跳过 SKU/价检,保留图片检。"""

    @pytest.fixture
    def crawled_product(self, sync_db, cat_tree, run_meta):
        """创建一个 source=alibaba 的商品,有图片无 SKU。"""
        slug_to_code = import_categories(sync_db, cat_tree)
        sync_db.flush()

        run = open_run(
            sync_db,
            run_key="test_publish",
            source="alibaba",
            operator=None,
            raw_path="/tmp",
            crawled_at=None,
        )
        sync_db.flush()

        offers = scan_offers(TEST_BATCH_DIR)
        vr = validate_batch(TEST_BATCH_DIR, run_meta, cat_tree, offers)
        valid = [o for o in offers if o.offer_id not in vr.offer_errors]
        offer = valid[0]

        static_root = Path("/tmp/test_ingest_static")
        static_root.mkdir(exist_ok=True)
        import_offer(
            sync_db, offer,
            slug_to_code=slug_to_code,
            leaf_lookup=build_leaf_lookup(cat_tree),
            run=run, run_meta=run_meta, static_root=static_root,
        )
        sync_db.flush()

        product = sync_db.execute(
            select(Product).where(Product.spu_code == f"P-{offer.offer_id}")
        ).scalar_one()
        return product

    def test_crawled_product_has_alibaba_source(self, crawled_product):
        assert crawled_product.source == "alibaba"
        assert crawled_product.status == ProductStatus.DRAFT

    def test_source_spread_from_run(self, crawled_product):
        """source 从 run.json 摊到每个商品。"""
        assert crawled_product.source == "alibaba"


# ---------- Phase 2: ingest run lifecycle ----------


class TestIngestRun:
    def test_open_close_run(self, sync_db):
        run = open_run(
            sync_db,
            run_key="test_lifecycle",
            source="test",
            operator="tester",
            raw_path="/tmp/test",
            crawled_at=None,
        )
        sync_db.flush()
        assert run.status == IngestRunStatus.RUNNING
        assert run.product_count == 0

        close_run(sync_db, run, status=IngestRunStatus.SUCCESS, product_count=5)
        sync_db.flush()
        assert run.status == IngestRunStatus.SUCCESS
        assert run.product_count == 5
        assert run.imported_at is not None

    def test_open_run_idempotent(self, sync_db):
        """同 run_key 重复 open → 复用,重置状态。"""
        run1 = open_run(
            sync_db, run_key="test_idem", source="test",
            operator=None, raw_path="/tmp", crawled_at=None,
        )
        sync_db.flush()
        close_run(sync_db, run1, status=IngestRunStatus.SUCCESS, product_count=3)
        sync_db.flush()

        run2 = open_run(
            sync_db, run_key="test_idem", source="test",
            operator=None, raw_path="/tmp", crawled_at=None,
        )
        sync_db.flush()
        assert run2.id == run1.id
        assert run2.status == IngestRunStatus.RUNNING
        assert run2.product_count == 0
