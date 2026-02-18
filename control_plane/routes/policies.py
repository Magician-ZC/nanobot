"""策略与配置 API 路由 - Skill/MCP Server 注册表、节点策略和配置管理"""

from fastapi import APIRouter, Depends, HTTPException, status

from control_plane.auth import get_current_user, require_admin
from control_plane.configs import get_node_config, get_node_config_with_llm_key, update_node_config
from control_plane.models import (
    MCPServerEntryCreate,
    MCPServerEntryResponse,
    NodeConfigResponse,
    NodeConfigUpdate,
    ResourcePolicyResponse,
    ResourcePolicyUpdate,
    SkillEntryCreate,
    SkillEntryResponse,
)
from control_plane.permissions import check_node_access
from control_plane.policies import (
    create_mcp_server,
    create_skill,
    get_node_policy,
    list_mcp_servers,
    list_skills,
    update_node_policy,
)

router = APIRouter()


# ── Skill 注册表 ──────────────────────────────────────────────────

@router.get("/api/skills", response_model=list[SkillEntryResponse])
async def list_skills_endpoint(_user: dict = Depends(get_current_user)):
    """列出全局 Skill 注册表"""
    skills = await list_skills()
    return [SkillEntryResponse(**s) for s in skills]


@router.post(
    "/api/skills",
    response_model=SkillEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_skill_endpoint(
    req: SkillEntryCreate, _admin: dict = Depends(require_admin)
):
    """注册新 Skill（仅 admin）"""
    try:
        skill = await create_skill(req.name, req.description, req.source)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e)
        )
    return SkillEntryResponse(**skill)


# ── MCP Server 注册表 ─────────────────────────────────────────────

@router.get("/api/mcp-servers", response_model=list[MCPServerEntryResponse])
async def list_mcp_servers_endpoint(_user: dict = Depends(get_current_user)):
    """列出全局 MCP Server 注册表"""
    servers = await list_mcp_servers()
    return [MCPServerEntryResponse(**s) for s in servers]


@router.post(
    "/api/mcp-servers",
    response_model=MCPServerEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_mcp_server_endpoint(
    req: MCPServerEntryCreate, _admin: dict = Depends(require_admin)
):
    """注册新 MCP Server（仅 admin）"""
    try:
        server = await create_mcp_server(
            req.name, req.connection_type, req.config, req.description
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e)
        )
    return MCPServerEntryResponse(**server)


# ── 节点策略 ──────────────────────────────────────────────────────

@router.get("/api/nodes/{id}/policy", response_model=ResourcePolicyResponse)
async def get_policy_endpoint(id: str, current_user: dict = Depends(get_current_user)):
    """获取节点资源策略（需要节点访问权限）"""
    await check_node_access(current_user, id)
    policy = await get_node_policy(id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found for this node",
        )
    return ResourcePolicyResponse(**policy)


@router.put("/api/nodes/{id}/policy", response_model=ResourcePolicyResponse)
async def update_policy_endpoint(
    id: str, req: ResourcePolicyUpdate, _admin: dict = Depends(require_admin)
):
    """更新节点资源策略（仅 admin），版本号自动递增"""
    try:
        policy = await update_node_policy(id, req.allowed_skills, req.allowed_mcp_servers)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        )
    return ResourcePolicyResponse(**policy)


# ── 节点配置 ──────────────────────────────────────────────────────

@router.get("/api/nodes/{id}/config", response_model=NodeConfigResponse)
async def get_config_endpoint(id: str, current_user: dict = Depends(get_current_user)):
    """获取节点配置（需要节点访问权限），自动注入分配的 LLM Key"""
    await check_node_access(current_user, id)
    config = await get_node_config_with_llm_key(id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Config not found for this node",
        )
    return NodeConfigResponse(**config)


@router.put("/api/nodes/{id}/config", response_model=NodeConfigResponse)
async def update_config_endpoint(
    id: str, req: NodeConfigUpdate, _admin: dict = Depends(require_admin)
):
    """更新节点配置（仅 admin），版本号自动递增"""
    try:
        config = await update_node_config(id, req.config_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        )
    return NodeConfigResponse(**config)
