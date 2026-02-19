"""消息路由器 - 根据飞书用户绑定关系分发消息到 Agent Node

管理节点 WebSocket 连接注册/注销，根据绑定关系路由消息，
处理未绑定和节点离线情况。

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
"""

import json
import re
from typing import Any

from loguru import logger

from control_plane.feishu_bind_code import verify_and_bind
from control_plane.feishu_binding import get_binding_by_open_id, update_binding_name
from control_plane.feishu_conversation import save_message
from control_plane.gateway_message import GatewayMessage

# 绑定码格式：6 位大写字母+数字
_BIND_CODE_PATTERN = re.compile(r"^[A-Z0-9]{6}$")


class MessageRouter:
    """消息路由 - 根据绑定关系分发消息到 Agent Node

    维护在线节点的 WebSocket 连接映射，实现入站/出站消息路由。
    """

    def __init__(self, gateway_service: Any = None):
        """初始化路由器

        Args:
            gateway_service: FeishuGatewayService 实例，用于回复飞书消息
        """
        self._gateway = gateway_service
        # node_id -> WebSocket 连接
        self._node_connections: dict[str, Any] = {}

    def set_gateway(self, gateway_service: Any) -> None:
        """设置网关服务引用（支持延迟注入）"""
        self._gateway = gateway_service

    # ── 节点连接管理 ──────────────────────────────────────────────

    def register_node_connection(self, node_id: str, websocket: Any) -> None:
        """注册节点 WebSocket 连接"""
        self._node_connections[node_id] = websocket
        logger.info(f"节点 {node_id} 已注册 WebSocket 连接")

    def unregister_node_connection(self, node_id: str) -> None:
        """注销节点 WebSocket 连接"""
        self._node_connections.pop(node_id, None)
        logger.info(f"节点 {node_id} 已注销 WebSocket 连接")

    def is_node_connected(self, node_id: str) -> bool:
        """检查节点是否在线（有活跃 WebSocket 连接）"""
        return node_id in self._node_connections

    @property
    def connected_node_count(self) -> int:
        """当前在线节点数"""
        return len(self._node_connections)

    # ── 入站消息路由（飞书 → Agent Node）─────────────────────────

    async def route_inbound(self, message: GatewayMessage) -> None:
        """路由入站消息到对应的 Agent Node

        流程：
        1. 存储入站消息到对话记录
        2. 根据 open_id 查找绑定关系
        3. 检查目标节点是否在线
        4. 转发消息到目标节点

        Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
        """
        feishu_open_id = message.feishu_open_id

        # 查找绑定关系 (Requirement 3.1)
        binding = await get_binding_by_open_id(feishu_open_id)

        if not binding:
            # 未绑定用户：先尝试绑定码匹配 (Requirements: 7.1, 7.3, 7.4, 7.5)
            await self._handle_unbound_user(feishu_open_id, message)
            return

        node_id = binding["node_id"]

        # 自动补全用户名（无需重新绑定）
        if not binding["feishu_name"] and message.feishu_name:
            await update_binding_name(feishu_open_id, message.feishu_name)
            logger.info(f"自动更新飞书用户名: {feishu_open_id} -> {message.feishu_name}")

        # 添加 reaction 表示已收到消息（点赞）
        if self._gateway and message.message_id:
            try:
                await self._gateway.add_reaction(message.message_id)
            except Exception as e:
                logger.debug(f"添加 reaction 失败: {e}")

        # 存储入站消息 (Requirement 5.1)
        await save_message(
            feishu_open_id=feishu_open_id,
            direction="inbound",
            content=message.content,
            node_id=node_id,
            msg_type=message.msg_type,
            status="pending",
        )

        # 检查节点是否在线
        if not self.is_node_connected(node_id):
            # 节点离线 (Requirement 3.4)
            logger.info(f"目标节点 {node_id} 离线，无法转发消息")
            await self._reply_feishu(
                feishu_open_id,
                "您绑定的 Agent 节点当前不在线，请稍后再试。",
            )
            return

        # 转发消息到目标节点 (Requirement 3.2, 3.5)
        ws = self._node_connections[node_id]
        try:
            await ws.send_json(message.to_dict())
            logger.debug(
                f"消息已转发: {feishu_open_id} -> 节点 {node_id}"
            )
        except Exception as e:
            logger.error(f"转发消息到节点 {node_id} 失败: {e}")
            # 连接可能已断开，清理
            self.unregister_node_connection(node_id)
            await self._reply_feishu(
                feishu_open_id,
                "消息转发失败，您绑定的节点连接异常，请稍后再试。",
            )

    # ── 出站消息路由（Agent Node → 飞书）─────────────────────────

    async def route_outbound(self, node_id: str, message: GatewayMessage) -> None:
        """路由出站消息（Agent Node 响应）到飞书

        Requirements: 4.5, 5.2
        """
        feishu_open_id = message.feishu_open_id
        chat_id = message.chat_id or feishu_open_id

        # 存储出站消息 (Requirement 5.2)
        await save_message(
            feishu_open_id=feishu_open_id,
            direction="outbound",
            content=message.content,
            node_id=node_id,
            msg_type=message.msg_type,
            status="pending",
        )

        # 通过飞书 API 发送
        success = await self._send_feishu_card(chat_id, message.content)
        if not success:
            logger.error(f"飞书消息发送失败: -> {feishu_open_id}")

    # ── 自助绑定流程 (Requirements: 7.1, 7.3, 7.4, 7.5) ────────

    async def _handle_unbound_user(
        self, feishu_open_id: str, message: GatewayMessage
    ) -> None:
        """处理未绑定用户的消息：检测绑定码或回复引导"""
        content = message.content.strip().upper()

        # 存储入站消息（无关联节点）
        await save_message(
            feishu_open_id=feishu_open_id,
            direction="inbound",
            content=message.content,
            msg_type=message.msg_type,
            status="delivered",
        )

        # 检查是否为绑定码格式
        if _BIND_CODE_PATTERN.match(content):
            binding = await verify_and_bind(
                content, feishu_open_id, message.feishu_name
            )
            if binding:
                # 绑定成功 (Requirement 7.5)
                node_id = binding["node_id"]
                logger.info(
                    f"飞书用户 {feishu_open_id} 通过绑定码绑定到节点 {node_id}"
                )
                await self._reply_feishu(
                    feishu_open_id,
                    f"绑定成功！您已绑定到节点 {node_id}，现在可以开始对话了。",
                )
                return
            else:
                # 绑定码无效/过期/已使用 (Requirement 7.4)
                await self._reply_feishu(
                    feishu_open_id,
                    "绑定码无效、已过期或已被使用，请联系管理员重新获取。",
                )
                return

        # 非绑定码，回复绑定引导 (Requirement 7.1)
        logger.info(f"飞书用户 {feishu_open_id} 未绑定任何节点")
        await self._reply_feishu(
            feishu_open_id,
            "您尚未绑定任何 Agent 节点。请联系管理员获取绑定码，"
            "然后直接发送 6 位绑定码完成绑定。",
        )

    # ── 内部辅助方法 ──────────────────────────────────────────────

    async def _reply_feishu(self, open_id: str, text: str) -> None:
        """通过飞书回复文本消息"""
        if not self._gateway:
            logger.warning("网关服务未设置，无法回复飞书消息")
            return
        content = json.dumps({"text": text}, ensure_ascii=False)
        await self._gateway.send_message(open_id, content, msg_type="text")

    async def _send_feishu_card(self, chat_id: str, content: str) -> bool:
        """通过飞书发送卡片消息（与 FeishuChannel.send 类似）"""
        if not self._gateway:
            logger.warning("网关服务未设置，无法发送飞书消息")
            return False
        card = {
            "config": {"wide_screen_mode": True},
            "elements": [{"tag": "markdown", "content": content}],
        }
        card_json = json.dumps(card, ensure_ascii=False)
        return await self._gateway.send_message(chat_id, card_json, msg_type="interactive")
