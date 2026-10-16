"""商城关键词检索:拉丁文按整词匹配 + 中文按 n-gram 片段匹配 + 相关度排序。

口径(详见 PR 说明):
- 关键词按空白切成词,**每个词都要命中**,顺序/位置不限。
- 拉丁文词(en/sw/型号):PostgreSQL 全文检索,走 products.search_tsv 的 GIN 索引。
  英文做词形归一(pipes→pipe);英文停用词(for/and…)忽略;带数字的词(m8、20mm)
  额外允许前缀命中(m8 → m8x20),规格型号常这样搜。
- 中文词:products.search_zh(单字+双字 n-gram)GIN 索引粗筛,再用 ILIKE 精确核对,
  结果与原子串匹配一致;1~2 字的中文词也能走索引(pg_trgm 需 ≥3 字符)。
- 整串关键词 ≥3 字符且不含空格时,额外按 SPU 编码 / 厂家型号做子串匹配(trigram 索引)。

性能边界(每条查询触达行数有上限,不随数据量增长):
- 总数最多数到 SEARCH_COUNT_CAP,超出显示「N+」。
- 命中 ≤ SEARCH_COUNT_CAP 才做相关度排序(打分行数有上限);更宽的词按上架时间走索引。
- 关键词结果最多翻到 SEARCH_MAX_RESULTS 条。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import and_, false, func, literal_column, or_
from sqlalchemy.sql.elements import ColumnElement

from app.db.models.product import Product

SEARCH_COUNT_CAP = 5000
SEARCH_MAX_RESULTS = 1000
_MAX_WORDS = 8

_CJK_RE = re.compile(r"[一-鿿]")
# 只允许字母数字和小数点的带数字词才做前缀匹配;其余字符交给 plainto_tsquery 自行切分
_PREFIXABLE_RE = re.compile(r"[0-9a-z.]+")


@dataclass(frozen=True)
class LatinWord:
    text: str
    prefix: bool  # 带数字:允许前缀命中


@dataclass(frozen=True)
class CjkWord:
    text: str
    grams: tuple[str, ...]  # 与 zh_ngrams() 口径一致:1 字取单字,≥2 字取全部双字


@dataclass(frozen=True)
class SearchTerms:
    latin: tuple[LatinWord, ...] = field(default_factory=tuple)
    cjk: tuple[CjkWord, ...] = field(default_factory=tuple)
    code: str | None = None  # 整串编码/型号子串匹配


_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")


def _cjk_grams(word: str) -> tuple[str, ...]:
    """按连续中文片段取 n-gram(与 zh_ngrams 只拼相邻汉字一致):单字片段取单字,其余取双字。"""
    grams: set[str] = set()
    for run in _CJK_RUN_RE.findall(word):
        if len(run) == 1:
            grams.add(run)
        else:
            grams.update(run[i:i + 2] for i in range(len(run) - 1))
    return tuple(sorted(grams))


def parse_keyword(keyword: str) -> SearchTerms:
    """把用户输入拆成检索词(纯函数)。"""
    stripped = keyword.strip()
    latin: list[LatinWord] = []
    cjk: list[CjkWord] = []
    for word in stripped.split()[:_MAX_WORDS]:
        if _CJK_RE.search(word):
            # 中英混写的词(如「PPR管」)按中文处理:ILIKE 核对整词,n-gram 只取中文片段粗筛
            cjk.append(CjkWord(text=word, grams=_cjk_grams(word)))
        else:
            lower = word.lower()
            latin.append(LatinWord(
                text=word,
                prefix=bool(_PREFIXABLE_RE.fullmatch(lower) and re.search(r"\d", lower)),
            ))
    code = stripped if len(stripped) >= 3 and not re.search(r"\s", stripped) else None
    return SearchTerms(latin=tuple(latin), cjk=tuple(cjk), code=code)


def _like_pattern(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


# 检索配置写成 SQL 常量(不走绑定参数),与 search_tsv 生成列表达式一致
def _code_match(text: str) -> list[ColumnElement]:
    """SPU 编码 / 厂家型号子串匹配(≥3 字符走 trigram 索引)。"""
    pattern = _like_pattern(text)
    return [
        Product.spu_code.ilike(pattern, escape="\\"),
        Product.manufacturer_model.ilike(pattern, escape="\\"),
    ]


_EN = literal_column("'english'::regconfig")
_SIMPLE = literal_column("'simple'::regconfig")


def _latin_query(word: LatinWord) -> ColumnElement:
    query = func.plainto_tsquery(_EN, word.text).op("||")(func.plainto_tsquery(_SIMPLE, word.text))
    if word.prefix:
        query = query.op("||")(func.to_tsquery(_SIMPLE, f"'{word.text.lower()}':*"))
    return query


def build_keyword_filter(terms: SearchTerms) -> tuple[ColumnElement, ColumnElement | None]:
    """返回 (WHERE 条件, 相关度排序表达式 | None)。"""
    conds: list[ColumnElement] = []
    queries: list[ColumnElement] = []
    for word in terms.latin:
        query = _latin_query(word)
        queries.append(query)
        # 英文停用词(for/and…)切词后为空:视为命中,不让它拖垮「全部命中」
        word_conds = [
            func.numnode(func.plainto_tsquery(_EN, word.text)) == 0,
            Product.search_tsv.op("@@")(query),
        ]
        if len(word.text) >= 3 and re.search(r"\d", word.text):
            # 带数字的词可能是编码:多词输入(如 "BR-36B 管")里也按 SPU 编码/型号子串匹配
            word_conds.extend(_code_match(word.text))
        conds.append(or_(*word_conds))
    if terms.latin and not terms.cjk:
        # 全是停用词(如只搜 "the")时不能退化成全表命中
        conds.append(or_(*(func.numnode(func.plainto_tsquery(_EN, w.text)) > 0 for w in terms.latin)))
    for word in terms.cjk:
        pattern = _like_pattern(word.text)
        word_match = or_(
            Product.name_zh.ilike(pattern, escape="\\"),
            Product.brand_zh.ilike(pattern, escape="\\"),
        )
        conds.append(and_(Product.search_zh.contains(list(word.grams)), word_match) if word.grams else word_match)

    where = and_(*conds) if conds else None
    if terms.code:
        code_match = or_(*_code_match(terms.code))
        where = code_match if where is None else or_(where, code_match)
    if where is None:  # 只有空白:调用方已判空,兜底不命中
        where = false()

    rank = None
    if queries:
        # 打分用 OR 连接:筛选已保证每个词命中;若用 AND,停用词(for 在向量里被丢弃)会让所有行得 0 分
        combined = queries[0]
        for query in queries[1:]:
            combined = combined.op("||")(query)
        rank = func.ts_rank_cd(Product.search_tsv, combined)
    return where, rank
