"""日志聚合 API 路由 - 日志上报、查询和清理"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from control_plane.auth import get_current_user, require_admin
from control_plane.logs import cleanup_old_logs, query_logs, store_logs
from control_plane.nodes import get_node_by_id

router = APIRouter()


# ── 请求/响应模型 ─────────────────────────────────────────────────

class LogEntryInput(BaseModel):
    """单条日志上报"""
    timestamp: str
    level: str = "INFO"
    message: str
    extra: dict | None = None


class LogBatchRequest(BaseModel):
    """批量日志上报请求"""
    logs: list[LogEntryInput] = Field(default_factory=list)


class LogEntryResponse(BaseModel):
    """日志条目响应"""
    id: str
    node_id: str
    timestamp: str
    level: str
    message: str
    extra: dict | None = None
    received_at: str


class LogStoreResult(BaseModel):
    """日志存储结果"""
    stored: int


class LogCleanupResult(BaseModel):
    """日志清理结果"""
    deleted: int


# ── 日志上报（节点调用，暂不校验 API Key） ────────────────────────

@router.post(
    "/api/nodes/{node_id}/logs",
    response_model=LogStoreResult,
    status_code=status.HTTP_201_CREATED,
)
async def receive_logs(node_id: str, req: LogBatchRequest):
    """Agent Node 批量上报日志"""
    node = await get_node_by_id(node_id)
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found",
        )
    count = await store_logs(node_id, [e.model_dump() for e in req.logs])
    return LogStoreResult(stored=count)


# ── 全局日志查询 ──────────────────────────────────────────────────

@router.get("/api/logs", response_model=list[LogEntryResponse])
async def get_global_logs(
    node_id: str | None = Query(default=None),
    level: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _user: dict = Depends(get_current_user),
):
    """全局日志查询，支持多维度过滤"""
    rows = await query_logs(
        node_id=node_id,
        level=level,
        keyword=keyword,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    return [LogEntryResponse(**r) for r in rows]


# ── 单节点日志查询 ────────────────────────────────────────────────

@router.get("/api/nodes/{node_id}/logs", response_model=list[LogEntryResponse])
async def get_node_logs(
    node_id: str,
    level: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _user: dict = Depends(get_current_user),
):
    """单节点日志查询"""
    node = await get_node_by_id(node_id)
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found",
        )
    rows = await query_logs(
        node_id=node_id,
        level=level,
        keyword=keyword,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    return [LogEntryResponse(**r) for r in rows]


# ── 日志清理（仅 admin） ─────────────────────────────────────────

@router.delete("/api/logs/cleanup", response_model=LogCleanupResult)
async def cleanup_logs(
    retention_days: int = Query(default=7, ge=1, le=365),
    _admin: dict = Depends(require_admin),
):
    """手动触发日志清理，删除超过保留期限的历史日志"""
    deleted = await cleanup_old_logs(retention_days)
    return LogCleanupResult(deleted=deleted)
