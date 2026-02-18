"""日志存储与查询逻辑 - 接收、存储和清理 Agent Node 上报的日志"""

import uuid
from datetime import datetime, timedelta, timezone

from control_plane.database import get_connection

# 默认日志保留天数
DEFAULT_RETENTION_DAYS = 7


async def store_logs(node_id: str, logs: list[dict]) -> int:
    """批量存储 Agent Node 上报的日志

    Args:
        node_id: 节点 ID
        logs: 日志条目列表，每条包含 timestamp, level, message, extra(可选)

    Returns:
        成功存储的日志条数
    """
    if not logs:
        return 0

    conn = await get_connection()
    try:
        now = datetime.now(timezone.utc).isoformat()
        count = 0
        for entry in logs:
            level = entry.get("level", "INFO").upper()
            if level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
                level = "INFO"
            extra = entry.get("extra")
            if extra is not None:
                import json
                extra = json.dumps(extra, ensure_ascii=False) if isinstance(extra, dict) else str(extra)

            await conn.execute(
                """INSERT INTO node_logs (id, node_id, timestamp, level, message, extra, received_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    node_id,
                    entry.get("timestamp", now),
                    level,
                    entry.get("message", ""),
                    extra,
                    now,
                ),
            )
            count += 1
        await conn.commit()
        return count
    finally:
        await conn.close()


async def query_logs(
    node_id: str | None = None,
    level: str | None = None,
    keyword: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """查询日志，支持多维度过滤

    Args:
        node_id: 按节点过滤
        level: 按日志级别过滤
        keyword: 按消息关键词模糊搜索
        start_time: 起始时间 (ISO 8601)
        end_time: 结束时间 (ISO 8601)
        limit: 返回条数上限
        offset: 分页偏移

    Returns:
        日志条目列表
    """
    conn = await get_connection()
    try:
        conditions: list[str] = []
        params: list = []

        if node_id:
            conditions.append("node_id = ?")
            params.append(node_id)
        if level:
            conditions.append("level = ?")
            params.append(level.upper())
        if keyword:
            conditions.append("message LIKE ?")
            params.append(f"%{keyword}%")
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time)
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
            SELECT id, node_id, timestamp, level, message, extra, received_at
            FROM node_logs {where}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        return [_row_to_log(row) for row in rows]
    finally:
        await conn.close()


async def cleanup_old_logs(retention_days: int = DEFAULT_RETENTION_DAYS) -> int:
    """清理超过保留期限的历史日志

    Args:
        retention_days: 保留天数，默认 7 天

    Returns:
        删除的日志条数
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "DELETE FROM node_logs WHERE timestamp < ?", (cutoff,)
        )
        await conn.commit()
        return cursor.rowcount
    finally:
        await conn.close()


def _row_to_log(row) -> dict:
    """将数据库行转换为日志字典"""
    import json

    extra = row[5]
    if isinstance(extra, str):
        try:
            extra = json.loads(extra)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "id": row[0],
        "node_id": row[1],
        "timestamp": row[2],
        "level": row[3],
        "message": row[4],
        "extra": extra,
        "received_at": row[6],
    }
