"""商城关键词检索:products 增加 search_tsv(拉丁文全文检索)/ search_zh(中文 n-gram)生成列 + GIN 索引"""
from alembic import op

revision = "search_0001_fulltext"
down_revision = "user_0001_email_normalized"
branch_labels = None
depends_on = None

# 迁移冻结自己的一份定义,不 import 应用代码;与 app/db/models/product.py 保持一致
_ZH_NGRAMS_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION zh_ngrams(t text) RETURNS text[]
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT coalesce(array_agg(DISTINCT g), '{}') FROM (
    SELECT substr(t, i, 1) AS g FROM generate_series(1, length(t)) AS i
    UNION ALL
    SELECT substr(t, i, 2) FROM generate_series(1, length(t) - 1) AS i
  ) s
  -- 按码点判断 CJK 统一汉字 U+4E00..U+9FFF(与 product_search._CJK_RE 一致),不依赖库 locale
  WHERE ascii(substr(g, 1, 1)) BETWEEN 19968 AND 40959
    AND (length(g) = 1 OR ascii(substr(g, 2, 1)) BETWEEN 19968 AND 40959)
$$
"""
_SEARCH_TSV_EXPR = (
    "setweight(to_tsvector('english'::regconfig, coalesce(name_en, '')), 'A') || "
    "setweight(to_tsvector('simple'::regconfig, coalesce(name_sw, '')), 'A') || "
    "setweight(to_tsvector('english'::regconfig, coalesce(brand_en, '')), 'B') || "
    "setweight(to_tsvector('simple'::regconfig, coalesce(manufacturer_model, '')), 'C')"
)
_SEARCH_ZH_EXPR = "zh_ngrams(coalesce(name_zh, '')) || zh_ngrams(coalesce(brand_zh, ''))"


def upgrade() -> None:
    op.execute(_ZH_NGRAMS_FUNCTION_SQL)
    # 两列一条 ALTER:整表只重写一次(持 ACCESS EXCLUSIVE 锁;生产约 1.2 万行,实测为秒级)
    op.execute(
        "ALTER TABLE products "
        f"ADD COLUMN search_tsv tsvector GENERATED ALWAYS AS ({_SEARCH_TSV_EXPR}) STORED, "
        f"ADD COLUMN search_zh text[] GENERATED ALWAYS AS ({_SEARCH_ZH_EXPR}) STORED"
    )
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_products_search_tsv "
            "ON products USING gin (search_tsv) WHERE deleted_at IS NULL"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_products_search_zh "
            "ON products USING gin (search_zh) WHERE deleted_at IS NULL"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_products_search_zh")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_products_search_tsv")
    op.execute("ALTER TABLE products DROP COLUMN search_zh, DROP COLUMN search_tsv")
    op.execute("DROP FUNCTION IF EXISTS zh_ngrams(text)")
