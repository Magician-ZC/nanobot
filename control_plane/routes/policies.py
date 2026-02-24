"""策略与配置 API 路由 - Skill/MCP Server 注册表、节点策略和配置管理"""

from fastapi import APIRouter, Depends, HTTPException, status

from control_plane.auth import get_current_user, get_current_user_or_node, require_admin
from control_plane.configs import get_node_config, get_node_config_with_llm_key, update_node_config
from control_plane.models import (
    MCPServerEntryCreate,
    MCPServerEntryResponse,
    MCPServerEntryUpdate,
    NodeConfigResponse,
    NodeConfigUpdate,
    ResourcePolicyResponse,
    ResourcePolicyUpdate,
    SkillEntryCreate,
    SkillEntryResponse,
    SkillEntryUpdate,
)
from control_plane.permissions import check_node_access
from control_plane.policies import (
    create_mcp_server,
    create_skill,
    delete_mcp_server,
    delete_skill,
    get_node_policy,
    list_mcp_servers,
    list_skills,
    update_mcp_server,
    update_node_policy,
    update_skill,
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


@router.put("/api/skills/{skill_id}", response_model=SkillEntryResponse)
async def update_skill_endpoint(
    skill_id: str, req: SkillEntryUpdate, _admin: dict = Depends(require_admin)
):
    """更新 Skill（仅 admin）"""
    try:
        result = await update_skill(
            skill_id, name=req.name, description=req.description, source=req.source
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Skill not found")
    return SkillEntryResponse(**result)


@router.delete("/api/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill_endpoint(skill_id: str, _admin: dict = Depends(require_admin)):
    """删除 Skill（仅 admin）"""
    success = await delete_skill(skill_id)
    if not success:
        raise HTTPException(status_code=404, detail="Skill not found")


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


@router.put("/api/mcp-servers/{server_id}", response_model=MCPServerEntryResponse)
async def update_mcp_server_endpoint(
    server_id: str, req: MCPServerEntryUpdate, _admin: dict = Depends(require_admin)
):
    """更新 MCP Server（仅 admin）"""
    try:
        result = await update_mcp_server(
            server_id, name=req.name, connection_type=req.connection_type,
            config=req.config, description=req.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="MCP Server not found")
    return MCPServerEntryResponse(**result)


@router.delete("/api/mcp-servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp_server_endpoint(server_id: str, _admin: dict = Depends(require_admin)):
    """删除 MCP Server（仅 admin）"""
    success = await delete_mcp_server(server_id)
    if not success:
        raise HTTPException(status_code=404, detail="MCP Server not found")


@router.post("/api/mcp-servers/test-connection")
async def test_mcp_connection(
    req: MCPServerEntryCreate, _admin: dict = Depends(require_admin)
):
    """测试 MCP Server 连接

    HTTP 类型：尝试 MCP 协议握手（JSON-RPC initialize）
    stdio 类型：检查命令是否存在
    """
    import shutil

    if req.connection_type == "http":
        url = (req.config or {}).get("url", "")
        if not url:
            return {"success": False, "message": "未配置 URL"}
        headers = dict((req.config or {}).get("headers", {}))

        import asyncio
        from contextlib import AsyncExitStack

        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamable_http_client
            import httpx

            async with AsyncExitStack() as stack:
                http_client = await stack.enter_async_context(
                    httpx.AsyncClient(headers=headers or None, follow_redirects=True, timeout=15)
                )
                read, write, _ = await asyncio.wait_for(
                    stack.enter_async_context(streamable_http_client(url, http_client=http_client)),
                    timeout=15,
                )
                session = await stack.enter_async_context(ClientSession(read, write))
                await asyncio.wait_for(session.initialize(), timeout=10)
                tools_result = await asyncio.wait_for(session.list_tools(), timeout=10)
                tool_count = len(tools_result.tools)
                tool_names = [t.name for t in tools_result.tools[:5]]
                preview = ", ".join(tool_names)
                if tool_count > 5:
                    preview += f" ... 等 {tool_count} 个"
                return {"success": True, "message": f"连接成功，{tool_count} 个工具: {preview}"}

        except ImportError:
            # MCP SDK 不可用，降级为简单 HTTP 探测
            import urllib.request
            import urllib.error
            try:
                req_obj = urllib.request.Request(url, headers={**headers, "Accept": "application/json, text/event-stream"}, method="GET")
                with urllib.request.urlopen(req_obj, timeout=10) as resp:
                    return {"success": True, "message": f"端口可达 (HTTP {resp.status})"}
            except urllib.error.HTTPError as e:
                if e.code < 500:
                    return {"success": True, "message": f"端口可达 (HTTP {e.code})"}
                return {"success": False, "message": f"HTTP {e.code}: {e.reason}"}
            except urllib.error.URLError as e:
                return {"success": False, "message": f"连接失败: {e.reason}"}
        except asyncio.TimeoutError:
            return {"success": False, "message": "连接超时"}
        except Exception as e:
            return {"success": False, "message": f"连接失败: {str(e)}"}

    elif req.connection_type == "stdio":
        command = (req.config or {}).get("command", "")
        if not command:
            return {"success": False, "message": "未配置命令"}
        if not shutil.which(command):
            return {"success": False, "message": f"命令 '{command}' 未找到"}

        # 使用 MCP SDK 真正连接测试
        import asyncio
        from contextlib import AsyncExitStack

        args = (req.config or {}).get("args", [])
        env_extra = (req.config or {}).get("env", {})

        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            env = {**__import__("os").environ, **env_extra} if env_extra else None
            params = StdioServerParameters(command=command, args=args, env=env)

            async with AsyncExitStack() as stack:
                read, write = await asyncio.wait_for(
                    stack.enter_async_context(stdio_client(params)),
                    timeout=30,
                )
                session = await stack.enter_async_context(ClientSession(read, write))
                await asyncio.wait_for(session.initialize(), timeout=15)
                tools_result = await asyncio.wait_for(session.list_tools(), timeout=10)
                tool_count = len(tools_result.tools)
                tool_names = [t.name for t in tools_result.tools[:5]]
                preview = ", ".join(tool_names)
                if tool_count > 5:
                    preview += f" ... 等 {tool_count} 个"
                return {
                    "success": True,
                    "message": f"连接成功，{tool_count} 个工具: {preview}",
                }

        except ImportError:
            return {"success": False, "message": "MCP SDK 未安装，无法测试 stdio 连接"}
        except asyncio.TimeoutError:
            return {"success": False, "message": "连接超时（MCP Server 未在规定时间内响应）"}
        except Exception as e:
            return {"success": False, "message": f"连接失败: {str(e)}"}

    return {"success": False, "message": f"不支持的连接类型: {req.connection_type}"}


# ── 节点策略 ──────────────────────────────────────────────────────

@router.get("/api/nodes/{id}/policy", response_model=ResourcePolicyResponse)
async def get_policy_endpoint(id: str, current_user: dict = Depends(get_current_user_or_node)):
    """获取节点资源策略（支持 JWT 用户认证或节点 API Key 认证）"""
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
async def get_config_endpoint(id: str, current_user: dict = Depends(get_current_user_or_node)):
    """获取节点配置（支持 JWT 用户认证或节点 API Key 认证），自动注入分配的 LLM Key"""
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
