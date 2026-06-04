"""qwen-plus 裸调(指向 DashScope 兼容端点)。"""
from __future__ import annotations

from openai import AsyncOpenAI


async def llm_extract_json(
    api_key: str,
    api_url: str,
    model: str,
    prompt: str,
    timeout: float = 30.0,
) -> str:
    """裸调 qwen-plus,要求返回 JSON 字符串。失败抛异常(由调用方捕获)。"""
    client = AsyncOpenAI(api_key=api_key, base_url=api_url)
    resp = await client.chat.completions.create(
        model=model,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
        timeout=timeout,
    )
    return resp.choices[0].message.content or ""
