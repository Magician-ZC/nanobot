"""任务锁管理逻辑 - 锁获取、释放、超时自动释放"""

import uuid
from datetime import datetime, timedelta, timezone

from control_plane.database import get_connection


async def acquire_task_lock(
    node_id: str,
    resource: str,
    description: str = "",
    timeout_minutes: int = 10,
) -> dict | None:
    """获取任务锁

    检查同一节点上是否已有相同资源的活跃锁，若有则拒绝。
    成功则创建锁记录并返回锁信息。

    Args:
        node_id: 节点 ID
        resource: 锁定的资源标识
        description: 任务描述
        timeout_minutes: 超时时间（分钟），默认 10 分钟

    Returns:
        锁信息字典，冲突时返回 None
    """
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    conn = await get_connection()
    try:
        # 检查同一节点上是否已有相同资源的活跃锁（未过期）
        cursor = await conn.execute(
            "SELECT id FROM task_locks WHERE node_id = ? AND resource = ? AND expires_at > ?",
            (node_id, resource, now_iso),
        )
        existing = await cursor.fetchone()
        if existing:
            return None  # 冲突，拒绝

        lock_id = str(uuid.uuid4())
        expires_at = (now + timedelta(minutes=timeout_minutes)).isoformat()

        await conn.execute(
            """INSERT INTO task_locks (id, node_id, resource, description, acquired_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (lock_id, node_id, resource, description, now_iso, expires_at),
        )
        await conn.commit()

        return {
            "id": lock_id,
            "node_id": node_id,
            "resource": resource,
            "description": description,
            "acquired_at": now_iso,
            "expires_at": expires_at,
        }
    finally:
        await conn.close()


async def release_task_lock(lock_id: str) -> bool:
    """释放任务锁

    Args:
        lock_id: 锁 ID

    Returns:
        是否成功释放（锁不存在返回 False）
    """
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "DELETE FROM task_locks WHERE id = ?", (lock_id,)
        )
        await conn.commit()
        return cursor.rowcount > 0
    finally:
        await conn.close()


async def cleanup_expired_locks() -> int:
    """清理所有已过期的任务锁

    在心跳处理中调用，自动释放超时的锁。

    Returns:
        清理的锁数量
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "DELETE FROM task_locks WHERE expires_at <= ?", (now_iso,)
        )
        await conn.commit()
        return cursor.rowcount
    finally:
        await conn.close()


async def list_active_locks(node_id: str | None = None) -> list[dict]:
    """列出活跃的任务锁（未过期）

    Args:
        node_id: 可选，按节点过滤

    Returns:
        活跃锁列表
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    conn = await get_connection()
    try:
        if node_id:
            cursor = await conn.execute(
                "SELECT id, node_id, resource, description, acquired_at, expires_at "
                "FROM task_locks WHERE node_id = ? AND expires_at > ? "
                "ORDER BY acquired_at",
                (node_id, now_iso),
            )
        else:
            cursor = await conn.execute(
                "SELECT id, node_id, resource, description, acquired_at, expires_at "
                "FROM task_locks WHERE expires_at > ? "
                "ORDER BY acquired_at",
                (now_iso,),
            )
        rows = await cursor.fetchall()
        return [_row_to_lock(row) for row in rows]
    finally:
        await conn.close()


async def get_task_lock(lock_id: str) -> dict | None:
    """根据 ID 查询任务锁"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, node_id, resource, description, acquired_at, expires_at "
            "FROM task_locks WHERE id = ?",
            (lock_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return _row_to_lock(row)
    finally:
        await conn.close()


def _row_to_lock(row) -> dict:
    """将数据库行转换为锁字典"""
    return {
        "id": row[0],
        "node_id": row[1],
        "resource": row[2],
        "description": row[3],
        "acquired_at": row[4],
        "expires_at": row[5],
    }
