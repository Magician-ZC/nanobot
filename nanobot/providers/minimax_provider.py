"""MiniMax Anthropic-compatible provider."""

from __future__ import annotations

from typing import Any

import httpx
import json_repair

from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest


class MinimaxProvider(LLMProvider):
    """MiniMax provider using Anthropic-compatible API."""

    def __init__(self, api_key: str = "", api_base: str = "https://api.minimaxi.com/anthropic/v1", default_model: str = "MiniMax-M2.5"):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self._client = httpx.AsyncClient(timeout=60.0)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
    ) -> LLMResponse:
        """Call MiniMax Anthropic-compatible API."""
        try:
            url = f"{self.api_base}/messages"
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }

            # 转换 OpenAI 格式的消息到 Anthropic 格式
            anthropic_messages = self._convert_to_anthropic_format(messages)

            payload = {
                "model": model or self.default_model,
                "messages": self._sanitize_empty_content(anthropic_messages),
                "max_tokens": max(1, max_tokens),
                "temperature": temperature,
            }

            if tools:
                # 转换 OpenAI 格式的 tools 到 Anthropic 格式
                anthropic_tools = []
                for tool in tools:
                    if tool.get("type") == "function" and "function" in tool:
                        func = tool["function"]
                        anthropic_tools.append({
                            "name": func["name"],
                            "description": func.get("description", ""),
                            "input_schema": func.get("parameters", {"type": "object", "properties": {}})
                        })
                
                if anthropic_tools:
                    payload["tools"] = anthropic_tools
                    payload["tool_choice"] = {"type": "auto"}

            # Debug logging
            from loguru import logger
            logger.debug(f"MiniMax API 请求: url={url}")
            logger.debug(f"MiniMax API 请求头: {headers}")
            logger.debug(f"MiniMax API 请求体: {payload}")

            response = await self._client.post(url, json=payload, headers=headers)
            
            # Log response for debugging
            logger.debug(f"MiniMax API 响应状态: {response.status_code}")
            logger.debug(f"MiniMax API 响应内容: {response.text[:500]}")
            
            response.raise_for_status()

            data = response.json()
            return self._parse_response(data)

        except Exception as e:
            from loguru import logger
            logger.error(f"MiniMax API 调用失败: {e}")
            return LLMResponse(content=f"Error: {e}", finish_reason="error")

    def _convert_to_anthropic_format(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """转换 OpenAI 格式的消息到 Anthropic 格式。
        
        主要处理：
        1. tool 角色的消息转换为 user 角色 + tool_result 内容块
        2. assistant 的 tool_calls 转换为 tool_use 内容块
        3. 过滤掉没有对应 tool_use 的 tool_result（避免 API 报错）
        """
        # 第一遍：收集所有 tool_use 的 ID
        tool_use_ids = set()
        for msg in messages:
            if msg.get("role") == "assistant":
                tool_calls = msg.get("tool_calls", [])
                for tc in tool_calls:
                    if tc.get("type") == "function":
                        tool_use_ids.add(tc.get("id", ""))
        
        # 第二遍：转换消息，过滤无效的 tool_result
        anthropic_messages = []
        
        for msg in messages:
            role = msg.get("role")
            
            # 处理 tool 角色消息（OpenAI 格式）-> user + tool_result（Anthropic 格式）
            if role == "tool":
                tool_call_id = msg.get("tool_call_id", "")
                # 只保留有对应 tool_use 的 tool_result
                if tool_call_id in tool_use_ids:
                    content = msg.get("content", "")
                    anthropic_messages.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_call_id,
                                "content": content
                            }
                        ]
                    })
            
            # 处理 assistant 消息
            elif role == "assistant":
                content_blocks = []
                
                # 添加文本内容
                text_content = msg.get("content")
                if text_content:
                    content_blocks.append({"type": "text", "text": text_content})
                
                # 转换 tool_calls 到 tool_use 格式
                tool_calls = msg.get("tool_calls", [])
                for tc in tool_calls:
                    if tc.get("type") == "function":
                        func = tc.get("function", {})
                        import json
                        arguments = func.get("arguments", "{}")
                        if isinstance(arguments, str):
                            try:
                                arguments = json.loads(arguments)
                            except:
                                arguments = {}
                        
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc.get("id", ""),
                            "name": func.get("name", ""),
                            "input": arguments
                        })
                
                anthropic_messages.append({
                    "role": "assistant",
                    "content": content_blocks if content_blocks else ""
                })
            
            # 其他消息直接保留
            else:
                anthropic_messages.append(msg)
        
        return anthropic_messages

    def _parse_response(self, data: dict) -> LLMResponse:
        """Parse MiniMax Anthropic-compatible response."""
        if "error" in data:
            return LLMResponse(
                content=f"Error: {data['error'].get('message', 'Unknown error')}",
                finish_reason="error",
            )

        content = ""
        tool_calls = []

        # Parse content blocks
        for block in data.get("content", []):
            if block.get("type") == "text":
                content = block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    ToolCallRequest(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        arguments=block.get("input", {}),
                    )
                )

        usage = data.get("usage", {})
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=data.get("stop_reason", "stop"),
            usage={
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            },
        )

    def get_default_model(self) -> str:
        return self.default_model
