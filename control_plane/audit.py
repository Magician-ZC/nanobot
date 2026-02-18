"""审计日志存储与查询逻辑 - 接收、存储和查询 Agent Node 上报的审计日志"""

import json
import uuid
from datetime import datetime, timezone

from control_plane.database import get_connection


async def store_audit_logs(node_id: str, logs: list[dict]) -> int:
    """批量存储 Agent Node 上报的审计日志

    Args:
        node_id: 节点 ID
        logs: 审计日志条目列表

    Returns:
        成功存储的条数
    """
    if not logs:
        return 0

    conn = await get_connection()
    try:
        now = datetime.now(timezone.utc).isoformat()
        count = 0
        for entry in logs:
            result = entry.get("result", "success")
            if result not in ("success", "failed", "denied"):
                result = "success"
            details = entry.get("details", {})
            if isinstance(details, dict):
                details = json.dumps(details, ensure_ascii=False)

            await conn.execute(
                """INSERT INTO audit_logs
                   (id, node_id, timestamp, operation_type, details, result, is_violation, received_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.get("id", str(uuid.uuid4())),
                    node_id,
                    entry.get("timestamp", now),
                    entry.get("operation_type", ""),
                    details,
                    result,
                    1 if entry.get("is_violation") else 0,
                    now,
                ),
            )
            count += 1
        await conn.commit()
        return count
    finally:
        await conn.close()


async def query_audit_logs(
    node_id: str | None = None,
    operation_type: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    violations_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """查询审计日志，支持多维度过滤

    Args:
        node_id: 按节点过滤
        operation_type: 按操作类型过滤
        start_time: 起始时间 (ISO 8601)
        end_time: 结束时间 (ISO 8601)
        violations_only: 仅返回违规记录
        limit: 返回条数上限
        offset: 分页偏移

    Returns:
        审计日志条目列表
    """
    conn = await get_connection()
    try:
        conditions: list[str] = []
        params: list = []

        if node_id:
            conditions.append("node_id = ?")
            params.append(node_id)
        if operation_type:
            conditions.append("operation_type = ?")
            params.append(operation_type)
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time)
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time)
        if violations_only:
            conditions.append("is_violation = 1")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
            SELECT id, node_id, timestamp, operation_type, details, result, is_violation, received_at
            FROM audit_logs {where}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        return [_row_to_audit(row) for row in rows]
    finally:
        await conn.close()


def _row_to_audit(row) -> dict:
    """将数据库行转换为审计日志字典"""
    details = row[4]
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "id": row[0],
        "node_id": row[1],
        "timestamp": row[2],
        "operation_type": row[3],
        "details": details,
        "result": row[5],
        "is_violation": bool(row[6]),
        "received_at": row[7],
    }
