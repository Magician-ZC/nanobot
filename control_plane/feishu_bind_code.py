"""飞书绑定码管理 - 生成和验证一次性绑定码"""

import random
import string
import uuid
from datetime import datetime, timedelta, timezone

from control_plane.database import get_connection
from control_plane.feishu_binding import create_binding


async def generate_code(node_id: str, expires_minutes: int = 30) -> dict:
    """为指定节点生成 6 位随机字母数字绑定码

    Requirements: 7.2
    """
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(minutes=expires_minutes)).isoformat()
    code_id = str(uuid.uuid4())

    conn = await get_connection()
    try:
        await conn.execute(
            """INSERT INTO feishu_bind_codes
               (id, code, node_id, is_used, expires_at, created_at)
               VALUES (?, ?, ?, 0, ?, ?)""",
            (code_id, code, node_id, expires_at, now.isoformat()),
        )
        await conn.commit()

        return {
            "id": code_id,
            "code": code,
            "node_id": node_id,
            "is_used": False,
            "expires_at": expires_at,
            "created_at": now.isoformat(),
        }
    finally:
        await conn.close()


async def verify_and_bind(
    code: str, feishu_open_id: str, feishu_name: str = ""
) -> dict | None:
    """验证绑定码并创建绑定

    成功返回绑定信息，失败（过期/已使用/不存在）返回 None。

    Requirements: 7.3, 7.4
    """
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, code, node_id, is_used, expires_at FROM feishu_bind_codes WHERE code = ?",
            (code,),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        code_id, _, node_id, is_used, expires_at = row

        # 已使用
        if is_used:
            return None

        # 已过期
        exp = datetime.fromisoformat(expires_at)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > exp:
            return None

        # 标记绑定码已使用
        await conn.execute(
            "UPDATE feishu_bind_codes SET is_used = 1 WHERE id = ?", (code_id,)
        )
        await conn.commit()
    finally:
        await conn.close()

    # 复用 BindingManager 创建绑定
    binding = await create_binding(feishu_open_id, node_id, feishu_name)
    return binding


async def list_active_codes(node_id: str | None = None) -> list[dict]:
    """列出未使用且未过期的绑定码"""
    now = datetime.now(timezone.utc).isoformat()
    conn = await get_connection()
    try:
        if node_id:
            cursor = await conn.execute(
                """SELECT id, code, node_id, is_used, expires_at, created_at
                   FROM feishu_bind_codes
                   WHERE is_used = 0 AND expires_at > ? AND node_id = ?
                   ORDER BY created_at DESC""",
                (now, node_id),
            )
        else:
            cursor = await conn.execute(
                """SELECT id, code, node_id, is_used, expires_at, created_at
                   FROM feishu_bind_codes
                   WHERE is_used = 0 AND expires_at > ?
                   ORDER BY created_at DESC""",
                (now,),
            )
        rows = await cursor.fetchall()
        return [_row_to_bind_code(row) for row in rows]
    finally:
        await conn.close()


def _row_to_bind_code(row) -> dict:
    """将数据库行转换为绑定码字典"""
    return {
        "id": row[0],
        "code": row[1],
        "node_id": row[2],
        "is_used": bool(row[3]),
        "expires_at": row[4],
        "created_at": row[5],
    }
