"""GatewayMessageClient - Agent Node 侧网关消息客户端

通过 WebSocket 与 Control Plane 通信，接收转发的飞书消息并返回处理结果。
将收到的 GatewayMessage 转换为 InboundMessage 注入 MessageBus，
监听 MessageBus 的 OutboundMessage 并转换为响应发回。

Requirements: 4.1, 4.2, 4.3, 4.4, 4.6, 4.7
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nanobot.bus.queue import MessageBus

logger = logging.getLogger(__name__)

# 网关通道标识，用于 MessageBus 的 channel 字段
GATEWAY_CHANNEL = "feishu_gateway"

# 重连参数
_INITIAL_RETRY_DELAY = 5
_MAX_RETRY_DELAY = 300
_PING_INTERVAL = 30
_PONG_TIMEOUT = 10


class GatewayMessageClient:
    """网关消息客户端 - Agent Node 侧

    通过 WebSocket 连接到 Control Plane 的 /api/gateway/ws 端点，
    认证后双向传输飞书消息。

    Requirements: 4.1, 4.2, 4.3, 4.4, 4.6, 4.7
    """

    def __init__(
        self,
        control_plane_url: str,
        api_key: str,
        node_id: str,
        bus: "MessageBus",
    ):
        self._base_url = control_plane_url.rstrip("/")
        self._api_key = api_key
        self._node_id = node_id
        self._bus = bus

        self._ws = None
        self._running = False
        self._connected = False
        self._tasks: list[asyncio.Task] = []

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── 生命周期 ──────────────────────────────────────────────────

    async def start(self) -> None:
        """建立 WebSocket 连接并开始接收消息

        Requirements: 4.1, 4.7
        """
        if self._running:
            logger.warning("GatewayMessageClient 已在运行中")
            return

        self._running = True

        # 订阅 outbound 消息
        self._bus.subscribe_outbound(GATEWAY_CHANNEL, self._on_outbound)

        # 启动重连循环
        task = asyncio.create_task(self._reconnect_loop())
        self._tasks.append(task)
        logger.info("GatewayMessageClient 已启动")

    async def stop(self) -> None:
        """关闭连接"""
        self._running = False
        self._connected = False

        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._tasks.clear()

        await self._close_ws()
        logger.info("GatewayMessageClient 已停止")

    # ── WebSocket 连接管理 ────────────────────────────────────────

    def _ws_url(self) -> str:
        """构建 WebSocket URL"""
        base = self._base_url
        if base.startswith("https://"):
            base = "wss://" + base[len("https://"):]
        elif base.startswith("http://"):
            base = "ws://" + base[len("http://"):]
        return f"{base}/api/gateway/ws"

    async def _connect_and_auth(self) -> bool:
        """建立 WebSocket 连接并完成认证

        Requirements: 4.1, 4.7
        """
        try:
            import websockets
            url = self._ws_url()
            logger.info("正在连接网关 WebSocket: %s", url)
            self._ws = await websockets.connect(url)

            # 发送认证消息
            auth_msg = json.dumps({
                "type": "auth",
                "node_id": self._node_id,
                "api_key": self._api_key,
            })
            await self._ws.send(auth_msg)

            # 等待认证响应
            raw = await asyncio.wait_for(self._ws.recv(), timeout=10)
            resp = json.loads(raw)

            if resp.get("type") == "auth_ok":
                self._connected = True
                logger.info("网关 WebSocket 认证成功")
                return True
            else:
                reason = resp.get("reason", "unknown")
                logger.error("网关 WebSocket 认证失败: %s", reason)
                await self._close_ws()
                return False

        except Exception as e:
            logger.error("网关 WebSocket 连接失败: %s", e)
            await self._close_ws()
            return False

    async def _close_ws(self) -> None:
        """安全关闭 WebSocket 连接"""
        self._connected = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

    # ── 重连循环 ──────────────────────────────────────────────────

    async def _reconnect_loop(self) -> None:
        """断线重连循环，指数退避

        Requirements: 4.6
        """
        retry_delay = _INITIAL_RETRY_DELAY

        while self._running:
            if not self._connected:
                ok = await self._connect_and_auth()
                if ok:
                    retry_delay = _INITIAL_RETRY_DELAY
                    # 启动消息接收和心跳
                    recv_task = asyncio.create_task(self._receive_loop())
                    ping_task = asyncio.create_task(self._ping_loop())
                    # 等待任一任务结束（意味着连接断开）
                    done, pending = await asyncio.wait(
                        [recv_task, ping_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for t in pending:
                        t.cancel()
                        try:
                            await t
                        except asyncio.CancelledError:
                            pass
                    await self._close_ws()
                    if not self._running:
                        break
                    logger.info("网关连接断开，将在 %ds 后重连", retry_delay)
                else:
                    logger.info("网关连接失败，将在 %ds 后重试", retry_delay)

            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, _MAX_RETRY_DELAY)

    # ── 消息接收 ──────────────────────────────────────────────────

    async def _receive_loop(self) -> None:
        """接收 WebSocket 消息并处理

        Requirements: 4.2, 4.3
        """
        while self._running and self._ws:
            try:
                raw = await self._ws.recv()
                data = json.loads(raw)
                await self._on_message(data)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if self._running:
                    logger.warning("网关消息接收异常: %s", e)
                break

    async def _on_message(self, data: dict) -> None:
        """处理收到的消息，将飞书消息注入 MessageBus

        Requirements: 4.3
        """
        msg_type = data.get("type", "")

        if msg_type == "pong":
            return

        if msg_type == "message":
            # 将 GatewayMessage 转换为 InboundMessage 注入 MessageBus
            from nanobot.bus.events import InboundMessage

            inbound = InboundMessage(
                channel=GATEWAY_CHANNEL,
                sender_id=data.get("feishu_open_id", ""),
                chat_id=data.get("chat_id", "") or data.get("feishu_open_id", ""),
                content=data.get("content", ""),
                media=data.get("media", []),
                metadata={
                    "message_id": data.get("message_id", ""),
                    "feishu_name": data.get("feishu_name", ""),
                    "feishu_open_id": data.get("feishu_open_id", ""),
                    "msg_type": data.get("msg_type", "text"),
                    "timestamp": data.get("timestamp", ""),
                },
            )
            await self._bus.publish_inbound(inbound)
            logger.debug("网关消息已注入 MessageBus: %s", data.get("message_id", ""))
        else:
            logger.debug("收到网关消息类型: %s", msg_type)

    # ── 响应发送 ──────────────────────────────────────────────────

    async def send_response(self, feishu_open_id: str, chat_id: str,
                            content: str, message_id: str = "",
                            media: list[str] | None = None) -> None:
        """发送响应消息回 Control Plane

        Requirements: 4.4
        """
        if not self._ws or not self._connected:
            logger.warning("网关未连接，无法发送响应")
            return

        resp = {
            "type": "response",
            "message_id": message_id,
            "feishu_open_id": feishu_open_id,
            "chat_id": chat_id,
            "content": content,
            "media": media or [],
        }
        try:
            await self._ws.send(json.dumps(resp, ensure_ascii=False))
            logger.debug("响应已发送: -> %s", feishu_open_id)
        except Exception as e:
            logger.error("发送响应失败: %s", e)

    async def _on_outbound(self, msg) -> None:
        """MessageBus outbound 订阅回调 - 将 OutboundMessage 转换为响应发回

        Requirements: 4.4
        """
        # 从 metadata 中提取飞书相关信息
        feishu_open_id = msg.metadata.get("feishu_open_id", "")
        message_id = msg.metadata.get("message_id", "")
        chat_id = msg.chat_id

        # 如果没有 feishu_open_id，用 chat_id 作为回退
        if not feishu_open_id:
            feishu_open_id = chat_id

        await self.send_response(
            feishu_open_id=feishu_open_id,
            chat_id=chat_id,
            content=msg.content,
            message_id=message_id,
            media=msg.media,
        )

    # ── 心跳保活 ──────────────────────────────────────────────────

    async def _ping_loop(self) -> None:
        """定期发送心跳保活"""
        while self._running and self._ws:
            try:
                await asyncio.sleep(_PING_INTERVAL)
                if self._ws and self._connected:
                    await self._ws.send(json.dumps({"type": "ping"}))
            except asyncio.CancelledError:
                raise
            except Exception:
                break
