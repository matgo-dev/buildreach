"""关键词拆词单测(纯逻辑,不连 DB)。"""
from __future__ import annotations

from app.services.product_search import CjkWord, LatinWord, parse_keyword


def test_latin_words_split_on_whitespace():
    terms = parse_keyword("  cement   42.5 ")
    assert terms.latin == (LatinWord("cement", prefix=False), LatinWord("42.5", prefix=True))
    assert terms.cjk == ()


def test_prefix_only_for_alnum_words_with_digits():
    terms = parse_keyword("M8 20mm pipe 6-7mm 1/2")
    assert [w.prefix for w in terms.latin] == [True, True, False, False, False]


def test_cjk_word_grams_single_char_and_bigrams():
    single, multi = parse_keyword("管 镀锌钢管").cjk
    assert single == CjkWord("管", grams=("管",))
    assert multi.text == "镀锌钢管" and set(multi.grams) == {"镀锌", "锌钢", "钢管"}


def test_mixed_word_uses_han_part_for_grams():
    (word,) = parse_keyword("PPR管").cjk
    assert word == CjkWord("PPR管", grams=("管",))


def test_code_match_only_for_single_token_of_three_chars_or_more():
    assert parse_keyword("BR-36B").code == "BR-36B"
    assert parse_keyword("m8").code is None
    assert parse_keyword("steel pipe").code is None


def test_words_capped_at_eight():
    assert len(parse_keyword(" ".join(f"w{i}" for i in range(12))).latin) == 8
