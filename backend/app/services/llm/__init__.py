"""LLM 服务层。

抽象基类 `LLMService` 暴露:
- `generate(prompt)` 同步生成,用于 AI 综合评价
- `stream_chat(messages)` 流式对话,用于追问

实现:`QwenChatService` 走 openai SDK + DashScope OpenAI 兼容端点。
后续切其他国产模型(DeepSeek / GLM / Moonshot 等)只需新增实现类。
"""
from app.services.llm.base import LLMService, LLMUnavailableError
from app.services.llm.qwen_chat_service import QwenChatService

__all__ = ["LLMService", "LLMUnavailableError", "QwenChatService"]
