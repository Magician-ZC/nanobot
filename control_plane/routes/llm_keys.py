"""LLM API Key 管理 API 路由"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from control_plane.auth import get_current_user, require_admin
from control_plane.llm_keys import (
    add_llm_key,
    allocate_key,
    check_usage_limits,
    delete_llm_key,
    get_llm_key,
    get_usage_summary,
    handle_ratelimit,
    list_llm_keys,
    query_token_usage,
    store_token_usage,
    update_llm_key,
)
from control_plane.models import (
    LLMKeyCreate,
    LLMKeyResponse,
    LLMKeyUpdate,
    RateLimitReport,
    TokenUsageBatchRequest,
    TokenUsageResponse,
    TokenUsageSummary,
)
from control_plane.nodes import get_node_by_id

router = APIRouter()


@router.post(
    "/api/llm-keys",
    response_model=LLMKeyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_llm_key(
    req: LLMKeyCreate,
    _admin: dict = Depends(require_admin),
):
    """添加 LLM API Key（仅 admin）"""
    result = await add_llm_key(
        name=req.name,
        provider=req.provider,
        api_key=req.api_key,
        max_concurrent=req.max_concurrent,
        usage_limit=req.usage_limit,
    )
    return LLMKeyResponse(**result)


@router.get("/api/llm-keys", response_model=list[LLMKeyResponse])
async def list_keys(_user: dict = Depends(get_current_user)):
    """列出所有 LLM Key（隐藏实际 Key 值）"""
    keys = await list_llm_keys()
    return [LLMKeyResponse(**k) for k in keys]


@router.put("/api/llm-keys/{key_id}", response_model=LLMKeyResponse)
async def update_key(
    key_id: str,
    req: LLMKeyUpdate,
    _admin: dict = Depends(require_admin),
):
    """更新 Key 配置（仅 admin）"""
    result = await update_llm_key(
        key_id,
        max_concurrent=req.max_concurrent,
        usage_limit=req.usage_limit,
        is_active=req.is_active,
        name=req.name,
    )
    if not result:
        raise HTTPException(status_code=404, detail="LLM Key not found")
    return LLMKeyResponse(**result)


@router.delete("/api/llm-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_key(key_id: str, _admin: dict = Depends(require_admin)):
    """删除 Key（仅 admin）"""
    success = await delete_llm_key(key_id)
    if not success:
        raise HTTPException(status_code=404, detail="LLM Key not found")


@router.post("/api/nodes/{node_id}/report-ratelimit")
async def report_ratelimit(
    node_id: str,
    req: RateLimitReport,
    _user: dict = Depends(get_current_user),
):
    """节点上报限流事件，触发 Key 切换"""
    node = await get_node_by_id(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    result = await handle_ratelimit(node_id, req.key_id)
    if not result:
        raise HTTPException(
            status_code=503,
            detail="No alternative LLM Key available",
        )
    return {"new_key_id": result["key_id"], "provider": result["provider"]}



@router.post("/api/nodes/{node_id}/token-usage")
async def receive_token_usage(node_id: str, req: TokenUsageBatchRequest):
    """接收节点批量上报的 Token 用量"""
    node = await get_node_by_id(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    records = [r.model_dump() for r in req.records]
    stored = await store_token_usage(node_id, records)

    # 检查是否有 Key 超限需要禁用
    await check_usage_limits()

    return {"stored": stored}



# ── Token 用量查询 ────────────────────────────────────────────────

@router.get("/api/token-usage", response_model=list[TokenUsageResponse])
async def get_global_usage(
    node_id: str | None = Query(default=None),
    key_id: str | None = Query(default=None),
    model: str | None = Query(default=None),
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    _user: dict = Depends(get_current_user),
):
    """全局 Token 用量查询（支持多维度过滤）"""
    records = await query_token_usage(
        node_id=node_id, key_id=key_id, model=model,
        start_time=start_time, end_time=end_time, limit=limit,
    )
    return [TokenUsageResponse(**r) for r in records]


@router.get("/api/token-usage/summary", response_model=TokenUsageSummary)
async def get_usage_summary_endpoint(
    node_id: str | None = Query(default=None),
    key_id: str | None = Query(default=None),
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
    _user: dict = Depends(get_current_user),
):
    """Token 用量汇总"""
    summary = await get_usage_summary(
        node_id=node_id, key_id=key_id,
        start_time=start_time, end_time=end_time,
    )
    return TokenUsageSummary(**summary)


@router.get("/api/nodes/{node_id}/token-usage", response_model=list[TokenUsageResponse])
async def get_node_usage(
    node_id: str,
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    _user: dict = Depends(get_current_user),
):
    """单节点 Token 用量查询"""
    node = await get_node_by_id(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    records = await query_token_usage(
        node_id=node_id, start_time=start_time, end_time=end_time, limit=limit,
    )
    return [TokenUsageResponse(**r) for r in records]


@router.get("/api/llm-keys/{key_id}/usage", response_model=TokenUsageSummary)
async def get_key_usage(
    key_id: str,
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
    _user: dict = Depends(get_current_user),
):
    """单 Key 用量汇总"""
    key = await get_llm_key(key_id)
    if not key:
        raise HTTPException(status_code=404, detail="LLM Key not found")
    summary = await get_usage_summary(
        key_id=key_id, start_time=start_time, end_time=end_time,
    )
    return TokenUsageSummary(**summary)

