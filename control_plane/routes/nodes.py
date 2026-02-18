"""节点管理 API 路由 - 注册令牌、节点注册、心跳、节点 CRUD"""

from fastapi import APIRouter, Depends, HTTPException, status

from control_plane.auth import get_current_user, require_admin
from control_plane.models import (
    HeartbeatResponse,
    NodeRegisterRequest,
    NodeRegisterResponse,
    NodeResponse,
    NodeStatus,
    RegistrationTokenCreate,
    RegistrationTokenResponse,
)
from control_plane.nodes import (
    create_registration_token,
    delete_node,
    get_node_by_id,
    list_nodes,
    process_heartbeat,
    register_node,
)
from control_plane.permissions import check_node_access
from control_plane.llm_keys import allocate_key

router = APIRouter()


# ── 注册令牌 ──────────────────────────────────────────────────────

@router.post(
    "/api/tokens",
    response_model=RegistrationTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_token(
    req: RegistrationTokenCreate,
    current_user: dict = Depends(get_current_user),
):
    """生成注册令牌

    admin 可为任意用户生成，operator 只能为自己生成。
    """
    # operator 只能为自己生成令牌
    if current_user["role"] != "admin" and req.user_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operators can only create tokens for themselves",
        )
    token = await create_registration_token(req.user_id)
    return RegistrationTokenResponse(**token)


# ── 节点注册（无需认证，使用注册令牌） ────────────────────────────

@router.post(
    "/api/nodes/register",
    response_model=NodeRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_node_endpoint(req: NodeRegisterRequest):
    """节点注册，使用一次性注册令牌"""
    try:
        result = await register_node(req.token, req.hostname)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # 注册成功后自动分配 LLM Key（如果 Key 池中有可用 Key）
    key_alloc = await allocate_key(result["node_id"])
    if key_alloc:
        result["llm_key_id"] = key_alloc["key_id"]

    return NodeRegisterResponse(**result)


# ── 心跳 ──────────────────────────────────────────────────────────

@router.post("/api/nodes/{id}/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(id: str, req: NodeStatus):
    """节点心跳上报

    注意：心跳接口使用节点 API Key 认证（简化实现中暂不校验，
    后续可通过中间件或依赖注入增加 API Key 验证）。
    """
    # 验证节点存在
    node = await get_node_by_id(id)
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found",
        )

    result = await process_heartbeat(id, req.model_dump())
    return HeartbeatResponse(**result)


# ── 节点列表 ──────────────────────────────────────────────────────

@router.get("/api/nodes", response_model=list[NodeResponse])
async def list_nodes_endpoint(current_user: dict = Depends(get_current_user)):
    """列出节点

    admin 可查看所有节点，operator 只能查看自己的节点。
    """
    if current_user["role"] == "admin":
        nodes = await list_nodes()
    else:
        nodes = await list_nodes(user_id=current_user["id"])
    return [NodeResponse(**n) for n in nodes]


# ── 节点详情 ──────────────────────────────────────────────────────

@router.get("/api/nodes/{id}", response_model=NodeResponse)
async def get_node_endpoint(id: str, current_user: dict = Depends(get_current_user)):
    """获取节点详情（需要节点访问权限）"""
    node = await check_node_access(current_user, id)
    return NodeResponse(**node)


# ── 删除节点 ──────────────────────────────────────────────────────

@router.delete("/api/nodes/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_node_endpoint(id: str, _admin: dict = Depends(require_admin)):
    """删除节点（仅 admin）"""
    success = await delete_node(id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found",
        )
