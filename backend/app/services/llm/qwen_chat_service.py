"""千问 qwen-plus 调用(openai SDK + DashScope OpenAI 兼容端点)。

为何不用 dashscope 原生 SDK:
- OpenAI Chat Completions 已成为国内外 LLM API 事实标准
- DeepSeek / GLM / Moonshot 等都提供同样的兼容端点
- 切换其他模型时只需改 base_url + api_key + model,无需重写调用代码
- 工单 §3.8 / ADR-0003 §二原写"dashscope SDK",在 C2 实施时改为 openai SDK,
  与项目 agent-dev-demo 栈保持一致(详见 ADR-0003 §三协议兼容理由)
"""
from __future__ import annotations

import logging
from typing import AsyncIterator

from openai import AsyncOpenAI
from openai import APIError, APIConnectionError, APITimeoutError, AuthenticationError

from app.core.config import Settings
from app.services.llm.base import LLMService, LLMUnavailableError

logger = logging.getLogger(__name__)


class QwenChatService(LLMService):
    """qwen-plus chat 实现。"""

    def __init__(self, settings: Settings) -> None:
        self._model = settings.QWEN_CHAT_MODEL
        self._temperature = settings.QWEN_CHAT_TEMPERATURE
        # 未配置 API key 时仍允许实例化,调用时才抛错(便于本地无 key 启动)
        self._configured = bool(settings.DASHSCOPE_API_KEY)
        self._client = AsyncOpenAI(
            api_key=settings.DASHSCOPE_API_KEY or "missing",
            base_url=settings.QWEN_BASE_URL,
            timeout=settings.QWEN_TIMEOUT_SECONDS,
        )

    def _check_configured(self) -> None:
        if not self._configured:
            # message 进服务端日志即可,绝对不要泄露具体 env 变量名给前端
            # (前端的固定文案在 credit.py SSE event 出口控制)
            raise LLMUnavailableError("LLM credentials not configured")

    async def generate(self, prompt: str) -> str:
        self._check_configured()
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                temperature=self._temperature,
                messages=[{"role": "user", "content": prompt}],
            )
        except (APIConnectionError, APITimeoutError, AuthenticationError, APIError) as exc:
            logger.warning("LLM generate 失败: %s", exc)
            raise LLMUnavailableError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception("LLM generate 未知错误")
            raise LLMUnavailableError(str(exc)) from exc

        content = resp.choices[0].message.content if resp.choices else None
        return (content or "").strip()

    async def generate_json(
        self,
        prompt: str,
        *,
        timeout_seconds: int | None = None,
    ) -> str:
        self._check_configured()
        try:
            # openai SDK 的 timeout 是客户端级,用 with_options 临时覆盖单次调用
            client = (
                self._client.with_options(timeout=timeout_seconds)
                if timeout_seconds is not None
                else self._client
            )
            resp = await client.chat.completions.create(
                model=self._model,
                temperature=0.0,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}],
            )
        except (APIConnectionError, APITimeoutError, AuthenticationError, APIError) as exc:
            logger.warning("LLM generate_json 失败: %s", exc)
            raise LLMUnavailableError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception("LLM generate_json 未知错误")
            raise LLMUnavailableError(str(exc)) from exc

        content = resp.choices[0].message.content if resp.choices else None
        return (content or "").strip()

    async def stream_chat(
        self, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        self._check_configured()
        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                temperature=self._temperature,
                messages=messages,  # type: ignore[arg-type]
                stream=True,
            )
        except (APIConnectionError, APITimeoutError, AuthenticationError, APIError) as exc:
            logger.warning("LLM stream_chat 失败: %s", exc)
            raise LLMUnavailableError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception("LLM stream_chat 未知错误")
            raise LLMUnavailableError(str(exc)) from exc

        try:
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content
        except (APIConnectionError, APITimeoutError, APIError) as exc:
            logger.warning("LLM stream_chat 中途断流: %s", exc)
            raise LLMUnavailableError(str(exc)) from exc
