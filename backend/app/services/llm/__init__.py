"""LLM 服务层。

抽象基类 `LLMService` 暴露:
- `generate(prompt)` 同步生成,用于 AI 综合评价
- `stream_chat(messages)` 流式对话,用于追问

实现:`QwenChatService` 走 openai SDK + DashScope OpenAI 兼容端点。
后续切其他国产模型(DeepSeek / GLM / Moonshot 等)只需新增实现类。

状态:目前仅测试环境使用,线上未配置 API key(见 config.DASHSCOPE_API_KEY)。
本层是轻量 chat 封装,尚未做成熟的 agent 编排(无 tool-calling / 多轮工具调用 /
重试与限流治理);后续引入 AI agent 时需在此之上扩展。
"""
from app.services.llm.base import LLMService, LLMUnavailableError
from app.services.llm.qwen_chat_service import QwenChatService

__all__ = ["LLMService", "LLMUnavailableError", "QwenChatService"]
