"""MCP client: connects to MCP servers and wraps their tools as native nanobot tools."""

import asyncio
from contextlib import AsyncExitStack
from typing import Any

from loguru import logger

from nanobot.agent.tools.base import Tool
from nanobot.agent.tools.registry import ToolRegistry


class MCPToolWrapper(Tool):
    """Wraps a single MCP server tool as a nanobot Tool."""

    def __init__(self, session, server_name: str, tool_def):
        self._session = session
        self._original_name = tool_def.name
        self._name = f"mcp_{server_name}_{tool_def.name}"
        self._description = tool_def.description or tool_def.name
        self._parameters = tool_def.inputSchema or {"type": "object", "properties": {}}

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters

    async def execute(self, **kwargs: Any) -> str:
        from mcp import types
        result = await self._session.call_tool(self._original_name, arguments=kwargs)
        parts = []
        for block in result.content:
            if isinstance(block, types.TextContent):
                parts.append(block.text)
            else:
                parts.append(str(block))
        return "\n".join(parts) or "(no output)"


async def _safe_close_stack(stack: AsyncExitStack, server_name: str) -> None:
    """安全关闭 AsyncExitStack，捕获 cancel scope 跨 task 等清理异常"""
    try:
        await stack.aclose()
    except (RuntimeError, BaseExceptionGroup, Exception) as e:
        logger.debug(f"MCP server '{server_name}': cleanup error (ignored): {e}")


async def connect_mcp_servers(
    mcp_servers: dict, registry: ToolRegistry, stack: AsyncExitStack
) -> None:
    """Connect to configured MCP servers and register their tools."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    for name, cfg in mcp_servers.items():
        try:
            logger.debug(f"MCP server '{name}': command={cfg.command}, args={cfg.args}, env_keys={list(cfg.env.keys()) if cfg.env else None}")
            
            # 使用独立的 exit stack 隔离每个 server 的连接，
            # 防止单个 server 连接失败的 cancel scope 污染主 stack
            server_stack = AsyncExitStack()
            connected = False
            
            try:
                if cfg.command and cfg.command.strip():
                    merged_env = None
                    if cfg.env:
                        import os
                        merged_env = {**os.environ, **cfg.env}
                    params = StdioServerParameters(
                        command=cfg.command, args=cfg.args, env=merged_env
                    )
                    read, write = await server_stack.enter_async_context(stdio_client(params))
                    connected = True
                elif cfg.url:
                    from mcp.client.streamable_http import streamable_http_client
                    read, write, _ = await server_stack.enter_async_context(
                        streamable_http_client(cfg.url)
                    )
                    connected = True
                else:
                    logger.warning(f"MCP server '{name}': no command or url configured, skipping")
                    await _safe_close_stack(server_stack, name)
                    continue
            except (Exception, asyncio.CancelledError, BaseExceptionGroup) as e:
                logger.error(f"MCP server '{name}': failed to start: {e}")
                await _safe_close_stack(server_stack, name)
                continue

            session = await server_stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            tools = await session.list_tools()
            for tool_def in tools.tools:
                wrapper = MCPToolWrapper(session, name, tool_def)
                registry.register(wrapper)
                logger.debug(f"MCP: registered tool '{wrapper.name}' from server '{name}'")

            # 连接成功，将 server_stack 托管到主 stack
            await stack.enter_async_context(server_stack)
            logger.info(f"MCP server '{name}': connected, {len(tools.tools)} tools registered")
        except (Exception, asyncio.CancelledError, BaseExceptionGroup) as e:
            logger.error(f"MCP server '{name}': failed to connect: {e}")
