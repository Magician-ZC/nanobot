"""对话记录存储 - 管理飞书对话消息的持久化和查询"""

import uuid
from datetime import datetime, timezone

from control_plane.database import get_connection


async def save_message(
    feishu_open_id: str,
    direction: str,
    content: str,
    node_id: str | None = None,
    msg_type: str = "text",
    status: str = "delivered",
    feishu_message_id: str | None = None,
) -> str:
    """存储消息记录，返回消息 ID

    Requirements: 5.1, 5.2, 5.5
    """
    message_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    conn = await get_connection()
    try:
        await conn.execute(
            """INSERT INTO feishu_conversations
               (id, feishu_open_id, node_id, direction, content,
                msg_type, status, feishu_message_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                message_id,
                feishu_open_id,
                node_id,
                direction,
                content,
                msg_type,
                status,
                feishu_message_id,
                now,
            ),
        )
        await conn.commit()
        return message_id
    finally:
        await conn.close()


async def list_messages(
    feishu_open_id: str | None = None,
    node_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """查询对话记录，支持按飞书用户、节点和时间范围筛选

    结果按 created_at 升序排列。

    Requirements: 5.3, 5.4
    """
    conditions: list[str] = []
    params: list = []

    if feishu_open_id is not None:
        conditions.append("feishu_open_id = ?")
        params.append(feishu_open_id)
    if node_id is not None:
        conditions.append("node_id = ?")
        params.append(node_id)
    if start_time is not None:
        conditions.append("created_at >= ?")
        params.append(start_time)
    if end_time is not None:
        conditions.append("created_at <= ?")
        params.append(end_time)

    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    sql = (
        "SELECT id, feishu_open_id, node_id, direction, content, "
        "msg_type, status, created_at "
        f"FROM feishu_conversations{where_clause} "
        "ORDER BY created_at ASC "
        "LIMIT ? OFFSET ?"
    )
    params.extend([limit, offset])

    conn = await get_connection()
    try:
        cursor = await conn.execute(sql, params)
        rows = await cursor.fetchall()
        return [_row_to_message(row) for row in rows]
    finally:
        await conn.close()


async def get_conversation(feishu_open_id: str, limit: int = 50) -> list[dict]:
    """获取某个飞书用户的完整对话记录，按时间升序

    Requirements: 5.3, 5.4
    """
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            """SELECT id, feishu_open_id, node_id, direction, content,
                      msg_type, status, created_at
               FROM feishu_conversations
               WHERE feishu_open_id = ?
               ORDER BY created_at ASC
               LIMIT ?""",
            (feishu_open_id, limit),
        )
        rows = await cursor.fetchall()
        return [_row_to_message(row) for row in rows]
    finally:
        await conn.close()

async def list_sessions(node_id: str | None = None) -> list[dict]:
    """获取会话列表（按用户分组），每个用户一条记录，包含最后消息和消息数"""
    conn = await get_connection()
    try:
        if node_id:
            cursor = await conn.execute(
                """SELECT c.feishu_open_id,
                          COALESCE(b.feishu_name, '') as feishu_name,
                          COUNT(*) as message_count,
                          MAX(c.created_at) as last_message_at,
                          c.node_id
                   FROM feishu_conversations c
                   LEFT JOIN feishu_user_bindings b ON c.feishu_open_id = b.feishu_open_id
                   WHERE c.node_id = ?
                   GROUP BY c.feishu_open_id
                   ORDER BY last_message_at DESC""",
                (node_id,),
            )
        else:
            cursor = await conn.execute(
                """SELECT c.feishu_open_id,
                          COALESCE(b.feishu_name, '') as feishu_name,
                          COUNT(*) as message_count,
                          MAX(c.created_at) as last_message_at,
                          c.node_id
                   FROM feishu_conversations c
                   LEFT JOIN feishu_user_bindings b ON c.feishu_open_id = b.feishu_open_id
                   GROUP BY c.feishu_open_id
                   ORDER BY last_message_at DESC"""
            )
        rows = await cursor.fetchall()
        return [
            {
                "feishu_open_id": row[0],
                "feishu_name": row[1],
                "message_count": row[2],
                "last_message_at": row[3],
                "node_id": row[4],
            }
            for row in rows
        ]
    finally:
        await conn.close()


async def get_conversation(feishu_open_id: str, limit: int = 50) -> list[dict]:
    """获取某个飞书用户的完整对话记录，按时间升序

    Requirements: 5.3, 5.4
    """
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            """SELECT id, feishu_open_id, node_id, direction, content,
                      msg_type, status, created_at
               FROM feishu_conversations
               WHERE feishu_open_id = ?
               ORDER BY created_at ASC
               LIMIT ?""",
            (feishu_open_id, limit),
        )
        rows = await cursor.fetchall()
        return [_row_to_message(row) for row in rows]
    finally:
        await conn.close()



# ── 内部辅助函数 ──────────────────────────────────────────────────


def _row_to_message(row) -> dict:
    """将数据库行转换为消息字典"""
    return {
        "id": row[0],
        "feishu_open_id": row[1],
        "node_id": row[2],
        "direction": row[3],
        "content": row[4],
        "msg_type": row[5],
        "status": row[6],
        "created_at": row[7],
    }
