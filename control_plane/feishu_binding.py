"""飞书用户绑定管理 - 管理飞书用户与 Agent Node 的绑定关系"""

import uuid
from datetime import datetime, timezone

from control_plane.database import get_connection


async def create_binding(
    feishu_open_id: str, node_id: str, feishu_name: str = ""
) -> dict:
    """创建或更新绑定

    如果 feishu_open_id 已存在绑定，则更新 node_id（重新绑定）。
    一个 node_id 可被多个飞书用户绑定。

    Requirements: 2.1, 2.2, 2.5, 2.6
    """
    now = datetime.now(timezone.utc).isoformat()
    conn = await get_connection()
    try:
        # 检查是否已存在该 open_id 的绑定
        cursor = await conn.execute(
            "SELECT id FROM feishu_user_bindings WHERE feishu_open_id = ?",
            (feishu_open_id,),
        )
        existing = await cursor.fetchone()

        if existing:
            # 更新绑定（重新绑定到新节点）
            binding_id = existing[0]
            await conn.execute(
                """UPDATE feishu_user_bindings
                   SET node_id = ?, feishu_name = ?, updated_at = ?
                   WHERE id = ?""",
                (node_id, feishu_name, now, binding_id),
            )
        else:
            # 创建新绑定
            binding_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO feishu_user_bindings
                   (id, feishu_open_id, feishu_name, node_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (binding_id, feishu_open_id, feishu_name, node_id, now, now),
            )
        await conn.commit()

        return await _get_binding_by_id(conn, binding_id)
    finally:
        await conn.close()


async def delete_binding(binding_id: str) -> bool:
    """删除绑定，返回是否成功

    Requirements: 2.3
    """
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "DELETE FROM feishu_user_bindings WHERE id = ?", (binding_id,)
        )
        await conn.commit()
        return cursor.rowcount > 0
    finally:
        await conn.close()


async def get_binding_by_open_id(feishu_open_id: str) -> dict | None:
    """根据飞书 open_id 查找绑定

    Requirements: 2.1, 3.1
    """
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            """SELECT b.id, b.feishu_open_id, b.feishu_name, b.node_id,
                      b.created_at, b.updated_at, COALESCE(n.hostname, '') as node_hostname
               FROM feishu_user_bindings b
               LEFT JOIN nodes n ON b.node_id = n.id
               WHERE b.feishu_open_id = ?""",
            (feishu_open_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return _row_to_binding(row)
    finally:
        await conn.close()


async def list_bindings(node_id: str | None = None) -> list[dict]:
    """列出绑定记录，可按节点筛选

    Requirements: 2.4, 2.5
    """
    conn = await get_connection()
    try:
        if node_id:
            cursor = await conn.execute(
                """SELECT b.id, b.feishu_open_id, b.feishu_name, b.node_id,
                          b.created_at, b.updated_at, COALESCE(n.hostname, '') as node_hostname
                   FROM feishu_user_bindings b
                   LEFT JOIN nodes n ON b.node_id = n.id
                   WHERE b.node_id = ?
                   ORDER BY b.created_at""",
                (node_id,),
            )
        else:
            cursor = await conn.execute(
                """SELECT b.id, b.feishu_open_id, b.feishu_name, b.node_id,
                          b.created_at, b.updated_at, COALESCE(n.hostname, '') as node_hostname
                   FROM feishu_user_bindings b
                   LEFT JOIN nodes n ON b.node_id = n.id
                   ORDER BY b.created_at"""
            )
        rows = await cursor.fetchall()
        return [_row_to_binding(row) for row in rows]
    finally:
        await conn.close()

async def update_binding_name(feishu_open_id: str, feishu_name: str) -> bool:
    """更新绑定记录中的飞书用户名（自动补全，无需重新绑定）"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            """UPDATE feishu_user_bindings
               SET feishu_name = ?, updated_at = ?
               WHERE feishu_open_id = ? AND (feishu_name IS NULL OR feishu_name = '')""",
            (feishu_name, datetime.now(timezone.utc).isoformat(), feishu_open_id),
        )
        await conn.commit()
        return cursor.rowcount > 0
    finally:
        await conn.close()



# ── 内部辅助函数 ──────────────────────────────────────────────────


async def _get_binding_by_id(conn, binding_id: str) -> dict:
    """通过 ID 获取绑定记录（内部使用，复用已有连接）"""
    cursor = await conn.execute(
        """SELECT b.id, b.feishu_open_id, b.feishu_name, b.node_id,
                  b.created_at, b.updated_at, COALESCE(n.hostname, '') as node_hostname
           FROM feishu_user_bindings b
           LEFT JOIN nodes n ON b.node_id = n.id
           WHERE b.id = ?""",
        (binding_id,),
    )
    row = await cursor.fetchone()
    return _row_to_binding(row)


def _row_to_binding(row) -> dict:
    """将数据库行转换为绑定字典"""
    return {
        "id": row[0],
        "feishu_open_id": row[1],
        "feishu_name": row[2],
        "node_id": row[3],
        "created_at": row[4],
        "updated_at": row[5],
        "node_hostname": row[6],
    }
