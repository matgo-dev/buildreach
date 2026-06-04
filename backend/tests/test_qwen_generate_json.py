"""QwenChatService.generate_json 单测(Δ7 Step 3)。

验证结构化抽取调用固定 temperature=0.0 + response_format=json_object,
timeout_seconds 通过 with_options 覆盖,未配置 key 时抛 LLMUnavailableError。
不真连 DashScope,mock openai client。
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.services.llm import LLMUnavailableError
from app.services.llm.qwen_chat_service import QwenChatService


def _make_service() -> QwenChatService:
    svc = QwenChatService(settings)
    svc._configured = True  # 绕过 key 检查(测试不真连上游)
    return svc


def _mock_response(content: str) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


async def test_generate_json_passes_temperature_and_response_format():
    svc = _make_service()
    create = AsyncMock(return_value=_mock_response('{"established_date": null}'))
    svc._client = MagicMock()
    svc._client.chat.completions.create = create

    out = await svc.generate_json("抽取这家公司")

    assert out == '{"established_date": null}'
    kwargs = create.call_args.kwargs
    assert kwargs["temperature"] == 0.0
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["model"] == settings.QWEN_CHAT_MODEL


async def test_generate_json_timeout_uses_with_options():
    svc = _make_service()
    create = AsyncMock(return_value=_mock_response("{}"))
    scoped_client = MagicMock()
    scoped_client.chat.completions.create = create
    svc._client = MagicMock()
    svc._client.with_options = MagicMock(return_value=scoped_client)

    await svc.generate_json("x", timeout_seconds=30)

    svc._client.with_options.assert_called_once_with(timeout=30)
    create.assert_awaited_once()


async def test_generate_json_unconfigured_raises():
    svc = QwenChatService(settings)
    svc._configured = False
    with pytest.raises(LLMUnavailableError):
        await svc.generate_json("x")
