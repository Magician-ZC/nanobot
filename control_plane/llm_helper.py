"""CP 端 LLM 调用辅助 — 从 Key 池获取可用 Key 并调用 LLM

用于记忆合并、记忆压缩等 CP 内部 LLM 任务。
"""

import logging

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# 默认 provider -> api_base 映射
_DEFAULT_API_BASES = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "minimax": "https://api.minimaxi.com/v1",
    "moonshot": "https://api.moonshot.cn/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
}

# 默认 provider -> model 映射
_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-20241022",
    "deepseek": "deepseek-chat",
    "minimax": "MiniMax-M2.5",
    "moonshot": "moonshot-v1-8k",
    "qwen": "qwen-plus",
}


async def _get_available_key() -> dict | None:
    """从 Key 池获取一个可用的 LLM Key（不分配给节点，仅 CP 内部使用）"""
    from control_plane.database import get_connection
    import base64

    conn = await get_connection()
    try:
        cursor = await conn.execute(
            """SELECT id, provider, api_key_encrypted, api_base
               FROM llm_key_pool
               WHERE is_active = 1
               ORDER BY current_concurrent ASC LIMIT 1"""
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "key_id": row[0],
            "provider": row[1],
            "api_key": base64.b64decode(row[2].encode()).decode(),
            "api_base": row[3] or "",
        }
    finally:
        await conn.close()


async def llm_chat(prompt: str, system: str = "", max_tokens: int = 4096) -> str | None:
    """调用 LLM 完成文本生成任务

    自动从 Key 池获取可用 Key，失败时返回 None。
    """
    key_info = await _get_available_key()
    if not key_info:
        logger.warning("CP 端无可用 LLM Key，无法执行 LLM 任务")
        return None

    provider = key_info["provider"]
    api_base = key_info["api_base"] or _DEFAULT_API_BASES.get(provider)
    model = _DEFAULT_MODELS.get(provider, "gpt-4o-mini")

    if not api_base:
        logger.warning("Provider '%s' 无 api_base 配置", provider)
        return None

    try:
        client = AsyncOpenAI(api_key=key_info["api_key"], base_url=api_base)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.3,
        )
        return resp.choices[0].message.content
    except Exception:
        logger.exception("CP 端 LLM 调用失败 (provider=%s)", provider)
        return None
