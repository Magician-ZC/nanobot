"""审计日志 API 路由 - 审计日志上报、查询"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from control_plane.audit import query_audit_logs, store_audit_logs
from control_plane.auth import get_current_user
from control_plane.nodes import get_node_by_id

router = APIRouter()


# ── 请求/响应模型 ─────────────────────────────────────────────────

class AuditEntryInput(BaseModel):
    """单条审计日志上报"""
    id: str = ""
    timestamp: str
    operation_type: str
    details: dict = Field(default_factory=dict)
    result: str = "success"
    is_violation: bool = False


class AuditBatchRequest(BaseModel):
    """批量审计日志上报请求"""
    logs: list[AuditEntryInput] = Field(default_factory=list)


class AuditEntryResponse(BaseModel):
    """审计日志条目响应"""
    id: str
    node_id: str
    timestamp: str
    operation_type: str
    details: dict = Field(default_factory=dict)
    result: str
    is_violation: bool
    received_at: str


class AuditStoreResult(BaseModel):
    """审计日志存储结果"""
    stored: int


# ── 审计日志上报（节点调用） ──────────────────────────────────────

@router.post(
    "/api/nodes/{node_id}/audit",
    response_model=AuditStoreResult,
    status_code=status.HTTP_201_CREATED,
)
async def receive_audit_logs(node_id: str, req: AuditBatchRequest):
    """Agent Node 批量上报审计日志"""
    node = await get_node_by_id(node_id)
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found",
        )
    count = await store_audit_logs(node_id, [e.model_dump() for e in req.logs])
    return AuditStoreResult(stored=count)


# ── 全局审计日志查询 ──────────────────────────────────────────────

@router.get("/api/audit", response_model=list[AuditEntryResponse])
async def get_global_audit(
    node_id: str | None = Query(default=None),
    operation_type: str | None = Query(default=None),
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _user: dict = Depends(get_current_user),
):
    """全局审计日志查询，支持多维度过滤"""
    rows = await query_audit_logs(
        node_id=node_id,
        operation_type=operation_type,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    return [AuditEntryResponse(**r) for r in rows]


# ── 单节点审计日志查询 ────────────────────────────────────────────

@router.get("/api/nodes/{node_id}/audit", response_model=list[AuditEntryResponse])
async def get_node_audit(
    node_id: str,
    operation_type: str | None = Query(default=None),
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _user: dict = Depends(get_current_user),
):
    """单节点审计日志查询"""
    node = await get_node_by_id(node_id)
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found",
        )
    rows = await query_audit_logs(
        node_id=node_id,
        operation_type=operation_type,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    return [AuditEntryResponse(**r) for r in rows]


# ── 安全违规记录查询 ─────────────────────────────────────────────

@router.get("/api/audit/violations", response_model=list[AuditEntryResponse])
async def get_violations(
    node_id: str | None = Query(default=None),
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _user: dict = Depends(get_current_user),
):
    """安全违规记录查询"""
    rows = await query_audit_logs(
        node_id=node_id,
        start_time=start_time,
        end_time=end_time,
        violations_only=True,
        limit=limit,
        offset=offset,
    )
    return [AuditEntryResponse(**r) for r in rows]
