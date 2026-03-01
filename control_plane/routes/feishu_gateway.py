"""飞书网关 API 路由 - 配置管理、绑定管理、绑定码、对话记录、WebSocket 端点"""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from loguru import logger

from control_plane.auth import require_admin
from control_plane.feishu_bind_code import generate_code, list_active_codes
from control_plane.feishu_binding import create_binding, delete_binding, list_bindings
from control_plane.feishu_conversation import get_conversation, list_messages, list_sessions
from control_plane.feishu_gateway import (
    get_gateway_config,
    get_gateway_config_raw,
    save_gateway_config,
)
from control_plane.gateway_message import GatewayMessage
from control_plane.models import (
    BindCodeCreate,
    BindCodeResponse,
    BindingCreate,
    BindingResponse,
    ConversationMessageResponse,
    FeishuGatewayConfigCreate,
    FeishuGatewayConfigResponse,
    GatewayStatusResponse,
    SessionResponse,
)
from control_plane.nodes import verify_node_api_key

router = APIRouter()

# 全局单例引用，由 app.py 启动时注入
_gateway_service = None
_message_router = None


def get_message_router():
    """获取 MessageRouter 实例（用于节点连接状态查询）"""
    return _message_router


def set_gateway_service(service) -> None:
    """注入 FeishuGatewayService 实例"""
    global _gateway_service
    _gateway_service = service


def set_message_router(router_instance) -> None:
    """注入 MessageRouter 实例"""
    global _message_router
    _message_router = router_instance


# ── 6.1 网关配置和状态 API ────────────────────────────────────────


@router.post(
    "/api/gateway/config",
    response_model=FeishuGatewayConfigResponse,
    status_code=status.HTTP_200_OK,
)
async def save_config(
    req: FeishuGatewayConfigCreate,
    _admin: dict = Depends(require_admin),
):
    """设置飞书网关配置（仅 admin）"""
    config = await save_gateway_config(
        app_id=req.app_id,
        app_secret=req.app_secret,
        encrypt_key=req.encrypt_key,
        verification_token=req.verification_token,
    )
    return FeishuGatewayConfigResponse(**config)


@router.get("/api/gateway/config", response_model=FeishuGatewayConfigResponse)
async def get_config(_admin: dict = Depends(require_admin)):
    """获取飞书网关配置（脱敏，仅 admin）"""
    config = await get_gateway_config()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gateway config not found",
        )
    return FeishuGatewayConfigResponse(**config)


@router.get("/api/gateway/status", response_model=GatewayStatusResponse)
async def get_status(_admin: dict = Depends(require_admin)):
    """获取飞书网关运行状态"""
    bindings = await list_bindings()
    connected_nodes = _message_router.connected_node_count if _message_router else 0

    return GatewayStatusResponse(
        is_connected=_gateway_service.is_connected if _gateway_service else False,
        connected_since=(
            _gateway_service.connected_since.isoformat()
            if _gateway_service and _gateway_service.connected_since
            else None
        ),
        last_message_at=(
            _gateway_service.last_message_at.isoformat()
            if _gateway_service and _gateway_service.last_message_at
            else None
        ),
        connected_nodes=connected_nodes,
        total_bindings=len(bindings),
    )


@router.post("/api/gateway/start", status_code=status.HTTP_200_OK)
async def start_gateway(_admin: dict = Depends(require_admin)):
    """启动飞书网关"""
    if not _gateway_service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gateway service not initialized",
        )
    config = await get_gateway_config_raw()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gateway config not found, please set config first",
        )
    await _gateway_service.start(
        app_id=config["app_id"],
        app_secret=config["app_secret"],
        encrypt_key=config.get("encrypt_key", ""),
        verification_token=config.get("verification_token", ""),
    )
    return {"message": "Gateway started"}


@router.post("/api/gateway/stop", status_code=status.HTTP_200_OK)
async def stop_gateway(_admin: dict = Depends(require_admin)):
    """停止飞书网关"""
    if not _gateway_service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gateway service not initialized",
        )
    await _gateway_service.stop()
    return {"message": "Gateway stopped"}


# ── 6.2 绑定管理 API ─────────────────────────────────────────────


@router.get("/api/gateway/bindings", response_model=list[BindingResponse])
async def list_bindings_endpoint(
    node_id: str | None = None,
    _admin: dict = Depends(require_admin),
):
    """列出所有绑定，可按 node_id 筛选"""
    bindings = await list_bindings(node_id=node_id)
    return [BindingResponse(**b) for b in bindings]


@router.post(
    "/api/gateway/bindings",
    response_model=BindingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_binding_endpoint(
    req: BindingCreate,
    _admin: dict = Depends(require_admin),
):
    """创建飞书用户绑定"""
    binding = await create_binding(
        feishu_open_id=req.feishu_open_id,
        node_id=req.node_id,
        feishu_name=req.feishu_name,
    )
    return BindingResponse(**binding)


@router.delete(
    "/api/gateway/bindings/{binding_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_binding_endpoint(
    binding_id: str,
    _admin: dict = Depends(require_admin),
):
    """删除绑定"""
    success = await delete_binding(binding_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Binding not found",
        )


# ── 6.3 绑定码 API ───────────────────────────────────────────────


@router.post(
    "/api/gateway/bind-codes",
    response_model=BindCodeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_bind_code(
    req: BindCodeCreate,
    _admin: dict = Depends(require_admin),
):
    """为指定节点生成绑定码"""
    code = await generate_code(
        node_id=req.node_id,
        expires_minutes=req.expires_minutes,
    )
    return BindCodeResponse(**code)


@router.get("/api/gateway/bind-codes", response_model=list[BindCodeResponse])
async def list_bind_codes(
    node_id: str | None = None,
    _admin: dict = Depends(require_admin),
):
    """列出有效绑定码"""
    codes = await list_active_codes(node_id=node_id)
    return [BindCodeResponse(**c) for c in codes]


# ── 6.4 对话记录查询 API ─────────────────────────────────────────


@router.get(
    "/api/gateway/sessions",
    response_model=list[SessionResponse],
)
async def list_sessions_endpoint(
    node_id: str | None = None,
    _admin: dict = Depends(require_admin),
):
    """获取会话列表（按用户分组），每个用户一条记录"""
    sessions = await list_sessions(node_id=node_id)
    return [SessionResponse(**s) for s in sessions]


@router.get(
    "/api/gateway/conversations",
    response_model=list[ConversationMessageResponse],
)
async def list_conversations(
    feishu_open_id: str | None = None,
    node_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _admin: dict = Depends(require_admin),
):
    """查询对话记录列表，支持按用户、节点、时间范围筛选"""
    messages = await list_messages(
        feishu_open_id=feishu_open_id,
        node_id=node_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    return [ConversationMessageResponse(**m) for m in messages]


@router.get(
    "/api/gateway/conversations/{feishu_open_id}",
    response_model=list[ConversationMessageResponse],
)
async def get_user_conversation(
    feishu_open_id: str,
    limit: int = 50,
    _admin: dict = Depends(require_admin),
):
    """获取某个飞书用户的对话详情"""
    messages = await get_conversation(feishu_open_id, limit=limit)
    return [ConversationMessageResponse(**m) for m in messages]


# ── 6.5 Agent Node WebSocket 端点 ────────────────────────────────

# 认证超时（秒）
_AUTH_TIMEOUT = 10
# 心跳间隔（秒）
_PING_INTERVAL = 30
# 兼容路径迁移告警去重（按客户端 host）
_LEGACY_WS_WARNED_HOSTS: set[str] = set()


@router.websocket("/api/gateway/ws")
async def gateway_ws(ws: WebSocket):
    """Agent Node WebSocket 连接端点"""
    await _gateway_ws_handler(ws, is_legacy_path=False)


@router.websocket("/ws")
async def gateway_ws_legacy(ws: WebSocket):
    """兼容旧版 Agent Node WebSocket 连接端点"""
    await _gateway_ws_handler(ws, is_legacy_path=True)


async def _gateway_ws_handler(ws: WebSocket, *, is_legacy_path: bool) -> None:
    """处理 Agent Node WebSocket 连接。"""
    path = ws.url.path
    client_host = ws.client.host if ws.client else "unknown"
    if is_legacy_path and client_host not in _LEGACY_WS_WARNED_HOSTS:
        _LEGACY_WS_WARNED_HOSTS.add(client_host)
        logger.warning(
            "检测到兼容 WebSocket 路径连接 path={} host={}，请迁移到 /api/gateway/ws",
            path,
            client_host,
        )

    await ws.accept()
    node_id: str | None = None

    try:
        # ── 认证阶段 ──
        node_id, _ = await _authenticate(ws)
        if not node_id:
            return

        # 注册到路由器
        if _message_router:
            _message_router.register_node_connection(node_id, ws)

        # ── 消息循环 ──
        await _message_loop(ws, node_id)

    except WebSocketDisconnect:
        logger.info("节点 {} WebSocket 断开 path={}", node_id or "unknown", path)
        if node_id and _message_router:
            _message_router.unregister_node_connection(node_id, reason="peer disconnected")
    except Exception as e:
        logger.error("节点 {} WebSocket 异常 path={} error={}", node_id or "unknown", path, e)
        if node_id and _message_router:
            _message_router.unregister_node_connection(node_id, reason=f"ws error: {e}")
    finally:
        if node_id and _message_router and _message_router.is_node_connected(node_id):
            _message_router.unregister_node_connection(node_id, reason="handler exit")


async def _authenticate(ws: WebSocket) -> tuple[str | None, str | None]:
    """处理 WebSocket 认证，返回 (node_id, failure_reason)"""
    path = ws.url.path

    try:
        raw = await asyncio.wait_for(ws.receive_json(), timeout=_AUTH_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning(
            "Gateway WS 认证失败 path={} node_id=- reason={}",
            path,
            "auth timeout",
        )
        await ws.send_json({"type": "auth_fail", "reason": "auth timeout"})
        await ws.close()
        return None, "auth timeout"

    if raw.get("type") != "auth":
        logger.warning(
            "Gateway WS 认证失败 path={} node_id={} reason={} first_type={}",
            path,
            raw.get("node_id", "") or "-",
            "expected auth message",
            raw.get("type", "") or "-",
        )
        await ws.send_json({"type": "auth_fail", "reason": "expected auth message"})
        await ws.close()
        return None, "expected auth message"

    node_id = raw.get("node_id", "")
    api_key = raw.get("api_key", "")

    node = await verify_node_api_key(node_id, api_key)
    if not node:
        logger.warning(
            "Gateway WS 认证失败 path={} node_id={} reason={}",
            path,
            node_id or "-",
            "invalid credentials",
        )
        await ws.send_json({"type": "auth_fail", "reason": "invalid credentials"})
        await ws.close()
        return None, "invalid credentials"

    await ws.send_json({"type": "auth_ok"})
    logger.info("节点 {} WebSocket 认证成功 path={}", node_id, path)
    return node_id, None


async def _message_loop(ws: WebSocket, node_id: str) -> None:
    """认证后的消息收发循环"""
    while True:
        data = await ws.receive_json()
        msg_type = data.get("type", "")

        if msg_type == "ping":
            await ws.send_json({"type": "pong"})

        elif msg_type == "response":
            # Agent Node 返回的响应，路由到飞书
            if _message_router:
                gw_msg = GatewayMessage.from_dict(data)
                await _message_router.route_outbound(node_id, gw_msg)

        else:
            logger.warning(f"节点 {node_id} 发送未知消息类型: {msg_type}")
