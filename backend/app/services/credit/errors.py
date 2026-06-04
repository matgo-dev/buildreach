"""信用评估自定义异常。"""
from __future__ import annotations


class CreditDataError(Exception):
    """数据源 / 评分输入异常的基类。"""


class CompanyNotFoundError(CreditDataError):
    """企业 ID 不存在。"""


class EvaluatorMissingError(CreditDataError):
    """rule.evaluator_key 在 EVALUATORS 字典里找不到对应函数。

    启动时会主动校验:发现孤儿规则只 WARNING,不阻断启动(见 ScoringEngine 启动校验)。
    评分时遇到孤儿规则视为该规则不命中,继续往下走。
    """
