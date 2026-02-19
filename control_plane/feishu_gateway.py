"""飞书网关核心服务 - 管理飞书 WebSocket 连接、消息收发、凭证加密存储

运行在 Control Plane 侧，统一接入飞书应用，接收所有消息后交由 MessageRouter 路由。
复用 nanobot/channels/feishu.py 中的 lark-oapi SDK 用法。

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 6.1, 6.4
"""

import asyncio
import base64
import json
import threading
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

from loguru import logger

from control_plane.database import get_connection
from control_plane.gateway_message import GatewayMessage

try:
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import (
        CreateMessageRequest,
        CreateMessageRequestBody,
        P2ImMessageReceiveV1,
    )
    FEISHU_AVAILABLE = True
except ImportError:
    FEISHU_AVAILABLE = False
    lark = None

# 消息类型显示映射（复用 feishu.py 的模式）
MSG_TYPE_MAP = {
    "image": "[image]",
    "audio": "[audio]",
    "file": "[file]",
    "sticker": "[sticker]",
}


# ── 凭证加密/脱敏工具函数 ─────────────────────────────────────────
# 复用 llm_keys.py 的简化加密模式（base64），保持项目一致性
# Requirements: 6.1, 6.4

def encrypt_secret(value: str) -> str:
    """加密存储凭证（简化实现，使用 base64 编码）"""
    return base64.b64encode(value.encode()).decode()


def decrypt_secret(encrypted: str) -> str:
    """解密凭证"""
    return base64.b64decode(encrypted.encode()).decode()


def mask_secret(value: str) -> str:
    """脱敏显示凭证，仅显示前 4 位和后 4 位"""
    if len(value) <= 8:
        return value[:2] + "****" + value[-2:] if len(value) > 4 else "****"
    return value[:4] + "****" + value[-4:]


# ── 消息解析（复用 feishu.py 的逻辑）──────────────────────────────

def _extract_post_text(content_json: dict) -> str:
    """从飞书 post（富文本）消息中提取纯文本

    支持两种格式：
    1. 直接格式: {"title": "...", "content": [...]}
    2. 本地化格式: {"zh_cn": {"title": "...", "content": [...]}}
    """
    def extract_from_lang(lang_content: dict) -> str | None:
        if not isinstance(lang_content, dict):
            return None
        title = lang_content.get("title", "")
        content_blocks = lang_content.get("content", [])
        if not isinstance(content_blocks, list):
            return None
        text_parts = []
        if title:
            text_parts.append(title)
        for block in content_blocks:
            if not isinstance(block, list):
                continue
            for element in block:
                if isinstance(element, dict):
                    tag = element.get("tag")
                    if tag == "text":
                        text_parts.append(element.get("text", ""))
                    elif tag == "a":
                        text_parts.append(element.get("text", ""))
                    elif tag == "at":
                        text_parts.append(f"@{element.get('user_name', 'user')}")
        return " ".join(text_parts).strip() if text_parts else None

    if "content" in content_json:
        result = extract_from_lang(content_json)
        if result:
            return result

    for lang_key in ("zh_cn", "en_us", "ja_jp"):
        lang_content = content_json.get(lang_key)
        result = extract_from_lang(lang_content)
        if result:
            return result

    return ""


def parse_feishu_message(data: "P2ImMessageReceiveV1") -> GatewayMessage | None:
    """将飞书消息事件解析为 GatewayMessage

    复用 feishu.py 的消息解析逻辑，提取 content、open_id、chat_id 等字段。
    Requirements: 1.4
    """
    try:
        event = data.event
        message = event.message
        sender = event.sender

        # 跳过机器人消息
        if sender.sender_type == "bot":
            return None

        sender_id = sender.sender_id.open_id if sender.sender_id else ""
        chat_id = message.chat_id
        chat_type = message.chat_type  # "p2p" or "group"
        msg_type = message.message_type

        # 解析消息内容
        if msg_type == "text":
            try:
                content = json.loads(message.content).get("text", "")
            except (json.JSONDecodeError, TypeError):
                content = message.content or ""
        elif msg_type == "post":
            try:
                content_json = json.loads(message.content)
                content = _extract_post_text(content_json)
            except (json.JSONDecodeError, TypeError):
                content = message.content or ""
        else:
            content = MSG_TYPE_MAP.get(msg_type, f"[{msg_type}]")

        if not content or not sender_id:
            return None

        # p2p 对话用 sender_id 作为 chat_id，群聊用群 chat_id
        reply_to = chat_id if chat_type == "group" else sender_id

        return GatewayMessage(
            message_id=message.message_id or str(uuid.uuid4()),
            feishu_open_id=sender_id,
            feishu_name="",  # SDK 事件中无用户名，后续可从绑定表获取
            chat_id=reply_to,
            content=content,
            msg_type=msg_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        logger.error(f"解析飞书消息失败: {e}")
        return None


# ── 网关配置 CRUD（含加密存储）────────────────────────────────────

async def save_gateway_config(
    app_id: str,
    app_secret: str,
    encrypt_key: str = "",
    verification_token: str = "",
) -> dict:
    """保存飞书网关配置，凭证加密存储

    如果已有配置则更新，否则创建新配置。
    Requirements: 6.1
    """
    now = datetime.now(timezone.utc).isoformat()
    encrypted_secret = encrypt_secret(app_secret)

    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id FROM feishu_gateway_config LIMIT 1"
        )
        existing = await cursor.fetchone()

        if existing:
            config_id = existing[0]
            await conn.execute(
                """UPDATE feishu_gateway_config
                   SET app_id = ?, app_secret_encrypted = ?,
                       encrypt_key = ?, verification_token = ?,
                       updated_at = ?
                   WHERE id = ?""",
                (app_id, encrypted_secret, encrypt_key, verification_token, now, config_id),
            )
        else:
            config_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO feishu_gateway_config
                   (id, app_id, app_secret_encrypted, encrypt_key,
                    verification_token, is_active, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
                (config_id, app_id, encrypted_secret, encrypt_key,
                 verification_token, now, now),
            )
        await conn.commit()
        return await _get_config_response(conn, config_id)
    finally:
        await conn.close()


async def get_gateway_config() -> dict | None:
    """获取飞书网关配置（凭证脱敏显示）

    Requirements: 6.4
    """
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            """SELECT id, app_id, app_secret_encrypted, encrypt_key,
                      verification_token, is_active, created_at, updated_at
               FROM feishu_gateway_config LIMIT 1"""
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return _row_to_config_response(row)
    finally:
        await conn.close()


async def get_gateway_config_raw() -> dict | None:
    """获取飞书网关配置（含解密凭证，内部使用）"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            """SELECT id, app_id, app_secret_encrypted, encrypt_key,
                      verification_token, is_active, created_at, updated_at
               FROM feishu_gateway_config WHERE is_active = 1 LIMIT 1"""
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "app_id": row[1],
            "app_secret": decrypt_secret(row[2]),
            "encrypt_key": row[3] or "",
            "verification_token": row[4] or "",
            "is_active": bool(row[5]),
        }
    finally:
        await conn.close()


async def _get_config_response(conn, config_id: str) -> dict:
    """通过 ID 获取配置响应（内部使用，复用已有连接）"""
    cursor = await conn.execute(
        """SELECT id, app_id, app_secret_encrypted, encrypt_key,
                  verification_token, is_active, created_at, updated_at
           FROM feishu_gateway_config WHERE id = ?""",
        (config_id,),
    )
    row = await cursor.fetchone()
    return _row_to_config_response(row)


def _row_to_config_response(row) -> dict:
    """将数据库行转换为脱敏配置响应"""
    app_secret_raw = decrypt_secret(row[2])
    return {
        "id": row[0],
        "app_id": row[1],
        "app_secret_preview": mask_secret(app_secret_raw),
        "encrypt_key_preview": mask_secret(row[3]) if row[3] else "",
        "is_active": bool(row[5]),
        "created_at": row[6],
        "updated_at": row[7],
    }


# ── FeishuGatewayService 核心服务 ─────────────────────────────────

# 消息回调类型：接收 GatewayMessage，返回 None
MessageCallback = Callable[[GatewayMessage], Coroutine[Any, Any, None]]


class FeishuGatewayService:
    """飞书网关服务 - 管理飞书 WebSocket 连接

    运行在 Control Plane 侧，统一接入飞书应用。
    复用 FeishuChannel 的 lark-oapi SDK 连接模式。

    Requirements: 1.1, 1.2, 1.3, 1.4, 1.5
    """

    def __init__(self):
        self._client: Any = None  # lark.Client，用于发送消息
        self._ws_client: Any = None  # lark.ws.Client，WebSocket 接收
        self._ws_thread: threading.Thread | None = None
        self._running = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._connected_since: datetime | None = None
        self._last_message_at: datetime | None = None
        self._on_message_callback: MessageCallback | None = None
        self._processed_ids: OrderedDict[str, None] = OrderedDict()

    def set_message_callback(self, callback: MessageCallback) -> None:
        """设置消息接收回调，由 MessageRouter 注册"""
        self._on_message_callback = callback

    @property
    def is_connected(self) -> bool:
        """当前连接状态"""
        return self._running and self._ws_thread is not None and self._ws_thread.is_alive()

    @property
    def connected_since(self) -> datetime | None:
        """连接建立时间"""
        return self._connected_since

    @property
    def last_message_at(self) -> datetime | None:
        """最近消息时间"""
        return self._last_message_at

    async def start(self, app_id: str, app_secret: str,
                    encrypt_key: str = "", verification_token: str = "") -> None:
        """启动飞书 WebSocket 连接

        Requirements: 1.1, 1.2, 1.3
        """
        if not FEISHU_AVAILABLE:
            logger.error("飞书 SDK 未安装，请运行: pip install lark-oapi")
            return

        if not app_id or not app_secret:
            logger.error("飞书 app_id 和 app_secret 未配置")
            return

        # 如果已在运行，先停止
        if self._running:
            await self.stop()

        self._running = True
        self._loop = asyncio.get_running_loop()

        # 创建 Lark 客户端（用于发送消息）
        self._client = lark.Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .log_level(lark.LogLevel.INFO) \
            .build()

        # 创建事件处理器
        event_handler = lark.EventDispatcherHandler.builder(
            encrypt_key or "",
            verification_token or "",
        ).register_p2_im_message_receive_v1(
            self._on_message_sync
        ).build()

        # 创建 WebSocket 客户端
        self._ws_client = lark.ws.Client(
            app_id,
            app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
        )

        # 在独立线程中运行 WebSocket，带指数退避重连
        # Requirements: 1.2, 1.3
        def run_ws():
            retry_delay = 5
            max_delay = 300
            while self._running:
                try:
                    self._connected_since = datetime.now(timezone.utc)
                    self._ws_client.start()
                except Exception as e:
                    logger.warning(f"飞书 WebSocket 错误: {e}")
                    self._connected_since = None
                if self._running:
                    import time
                    logger.info(f"飞书 WebSocket 将在 {retry_delay}s 后重连")
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, max_delay)

        self._ws_thread = threading.Thread(target=run_ws, daemon=True)
        self._ws_thread.start()
        logger.info("飞书网关已启动 WebSocket 长连接")

    async def stop(self) -> None:
        """停止连接并释放资源

        Requirements: 1.5
        """
        self._running = False
        if self._ws_client:
            try:
                self._ws_client.stop()
            except Exception as e:
                logger.warning(f"停止 WebSocket 客户端出错: {e}")
        self._ws_client = None
        self._client = None
        self._ws_thread = None
        self._connected_since = None
        logger.info("飞书网关已停止")

    async def get_user_name(self, open_id: str) -> str:
        """通过飞书 API 获取用户名称"""
        if not self._client:
            return ""
        try:
            from lark_oapi.api.contact.v3 import GetUserRequest
            request = GetUserRequest.builder() \
                .user_id(open_id) \
                .user_id_type("open_id") \
                .build()
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None, self._client.contact.v3.user.get, request
            )
            if response.success() and response.data and response.data.user:
                return response.data.user.name or ""
        except Exception as e:
            logger.debug(f"获取飞书用户名失败: {e}")
        return ""

    async def send_message(self, open_id: str, content: str,
                           msg_type: str = "interactive") -> bool:
        """通过飞书 API 发送消息给指定用户

        Requirements: 4.5
        """
        if not self._client:
            logger.warning("飞书客户端未初始化，无法发送消息")
            return False

        try:
            # 确定 receive_id_type
            if open_id.startswith("oc_"):
                receive_id_type = "chat_id"
            else:
                receive_id_type = "open_id"

            request = CreateMessageRequest.builder() \
                .receive_id_type(receive_id_type) \
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(open_id)
                    .msg_type(msg_type)
                    .content(content)
                    .build()
                ).build()

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None, self._client.im.v1.message.create, request
            )

            if not response.success():
                logger.error(
                    f"飞书消息发送失败: code={response.code}, msg={response.msg}"
                )
                return False

            logger.debug(f"飞书消息已发送至 {open_id}")
            return True
        except Exception as e:
            logger.error(f"发送飞书消息出错: {e}")
            return False
    async def add_reaction(self, message_id: str, emoji_type: str = "THUMBSUP") -> bool:
        """为飞书消息添加 reaction（点赞），复用 feishu.py 的模式"""
        if not self._client:
            return False
        try:
            from lark_oapi.api.im.v1 import (
                CreateMessageReactionRequest,
                CreateMessageReactionRequestBody,
                Emoji,
            )
            request = CreateMessageReactionRequest.builder() \
                .message_id(message_id) \
                .request_body(
                    CreateMessageReactionRequestBody.builder()
                    .reaction_type(Emoji.builder().emoji_type(emoji_type).build())
                    .build()
                ).build()
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None, self._client.im.v1.message_reaction.create, request
            )
            if not response.success():
                logger.debug(f"添加 reaction 失败: code={response.code}, msg={response.msg}")
                return False
            return True
        except Exception as e:
            logger.debug(f"添加 reaction 出错: {e}")
            return False

    async def send_message(self, open_id: str, content: str,
                           msg_type: str = "interactive") -> bool:
        """通过飞书 API 发送消息给指定用户

        Requirements: 4.5
        """
        if not self._client:
            logger.warning("飞书客户端未初始化，无法发送消息")
            return False

        try:
            # 确定 receive_id_type
            if open_id.startswith("oc_"):
                receive_id_type = "chat_id"
            else:
                receive_id_type = "open_id"

            request = CreateMessageRequest.builder() \
                .receive_id_type(receive_id_type) \
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(open_id)
                    .msg_type(msg_type)
                    .content(content)
                    .build()
                ).build()

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None, self._client.im.v1.message.create, request
            )

            if not response.success():
                logger.error(
                    f"飞书消息发送失败: code={response.code}, msg={response.msg}"
                )
                return False

            logger.debug(f"飞书消息已发送至 {open_id}")
            return True
        except Exception as e:
            logger.error(f"发送飞书消息出错: {e}")
            return False

    def _on_message_sync(self, data: "P2ImMessageReceiveV1") -> None:
        """同步消息回调（从 WebSocket 线程调用），调度到主事件循环"""
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._on_message(data), self._loop)

    async def _on_message(self, data: "P2ImMessageReceiveV1") -> None:
        """处理接收到的飞书消息

        Requirements: 1.4
        """
        try:
            # 去重检查
            message_id = data.event.message.message_id
            if message_id in self._processed_ids:
                return
            self._processed_ids[message_id] = None
            while len(self._processed_ids) > 1000:
                self._processed_ids.popitem(last=False)

            # 解析消息
            gw_msg = parse_feishu_message(data)
            if not gw_msg:
                return

            # 获取飞书用户名（如果解析时未获取到）
            if not gw_msg.feishu_name:
                gw_msg.feishu_name = await self.get_user_name(gw_msg.feishu_open_id)

            self._last_message_at = datetime.now(timezone.utc)

            # 调用消息回调（由 MessageRouter 处理路由）
            if self._on_message_callback:
                await self._on_message_callback(gw_msg)
            else:
                logger.warning("飞书网关收到消息但未设置回调")
        except Exception as e:
            logger.error(f"处理飞书网关消息出错: {e}")
