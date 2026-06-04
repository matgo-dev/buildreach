"""LLMService 抽象基类(信用评估 §3.4 + ADR-0003)。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator


class LLMUnavailableError(Exception):
    """LLM 上游调用失败(网络 / 鉴权 / 限流 / 服务端错误等)。

    调用方决定如何降级:
    - AISummaryGenerator → 返回 None,ai_summary 字段留 null,前端展示"AI 评价暂时不可用"
    - 对话追问接口 → 返回错误 + 不阻断会话
    """


class LLMService(ABC):
    """LLM 服务抽象。"""

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """同步生成。输入纯 prompt,输出完整文本。

        失败时抛 LLMUnavailableError。
        """

    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        *,
        timeout_seconds: int | None = None,
    ) -> str:
        """结构化 JSON 输出(Δ7 公开数据抽取专用)。

        实现需保证:
        - 固定 temperature=0.0(抽取任务不要发散)
        - 启用 response_format={"type": "json_object"}
        - 返回原始 JSON 字符串(调用方负责 schema 校验与解析)
        - 失败抛 LLMUnavailableError
        """

    @abstractmethod
    async def stream_chat(
        self, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        """流式对话。messages 格式 [{"role": "system|user|assistant", "content": "..."}]。

        返回异步 generator,逐 chunk yield 字符串片段。失败时抛 LLMUnavailableError。
        """
        # ABC + AsyncIterator 协议在 mypy/runtime 上略尴尬:这里写 yield 形成 async generator 签名
        # 实现类按相同签名重写即可。
        if False:  # pragma: no cover
            yield ""
