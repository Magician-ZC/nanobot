"""LLM API Key 池管理 - Key CRUD、负载均衡分配、限流处理、用量统计"""

import json
import uuid
from collections import Counter
from datetime import datetime, timezone

from control_plane.database import get_connection

# 简单的对称加密（生产环境应使用 Fernet 或 AES）
# 这里使用 base64 编码模拟加密存储，保持与项目其他模块一致的简化风格
import base64


class KeyAssignmentError(Exception):
    """手动分配 LLM Key 失败"""


class KeyAssignmentNotFoundError(KeyAssignmentError):
    """节点或 Key 不存在"""


class KeyAssignmentConflictError(KeyAssignmentError):
    """分配冲突（已有其他绑定且不允许替换）"""


class KeyAssignmentCapacityError(KeyAssignmentError):
    """目标 Key 容量不足"""


def _encrypt_key(api_key: str) -> str:
    """加密存储 API Key（简化实现，使用 base64 编码）"""
    return base64.b64encode(api_key.encode()).decode()


def _decrypt_key(encrypted: str) -> str:
    """解密 API Key"""
    return base64.b64decode(encrypted.encode()).decode()


def _mask_key(api_key: str) -> str:
    """隐藏 Key 值，仅显示前 4 位"""
    if len(api_key) <= 4:
        return api_key + "****"
    return api_key[:4] + "****"


# ── Key CRUD ──────────────────────────────────────────────────────

async def add_llm_key(
    name: str,
    provider: str,
    api_key: str,
    max_concurrent: int = 5,
    usage_limit: int = 0,
) -> dict:
    """添加 LLM API Key 到 Key 池"""
    key_id = str(uuid.uuid4())
    encrypted = _encrypt_key(api_key)
    now = datetime.now(timezone.utc).isoformat()

    conn = await get_connection()
    try:
        await conn.execute(
            """INSERT INTO llm_key_pool
               (id, name, provider, api_key_encrypted, max_concurrent,
                current_concurrent, usage_limit, total_usage, is_active, created_at)
               VALUES (?, ?, ?, ?, ?, 0, ?, 0, 1, ?)""",
            (key_id, name, provider, encrypted, max_concurrent, usage_limit, now),
        )
        await conn.commit()
        return {
            "id": key_id,
            "name": name,
            "provider": provider,
            "api_key_preview": _mask_key(api_key),
            "max_concurrent": max_concurrent,
            "current_concurrent": 0,
            "usage_limit": usage_limit,
            "total_usage": 0,
            "is_active": True,
            "created_at": now,
        }
    finally:
        await conn.close()


async def list_llm_keys() -> list[dict]:
    """列出所有 Key（隐藏实际 Key 值）"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            """SELECT id, name, provider, api_key_encrypted, max_concurrent,
                      current_concurrent, usage_limit, total_usage, is_active, created_at
               FROM llm_key_pool ORDER BY created_at"""
        )
        rows = await cursor.fetchall()
        return [_row_to_key(row) for row in rows]
    finally:
        await conn.close()


async def get_llm_key(key_id: str) -> dict | None:
    """获取单个 Key 详情（隐藏实际 Key 值）"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            """SELECT id, name, provider, api_key_encrypted, max_concurrent,
                      current_concurrent, usage_limit, total_usage, is_active, created_at
               FROM llm_key_pool WHERE id = ?""",
            (key_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return _row_to_key(row)
    finally:
        await conn.close()


async def update_llm_key(
    key_id: str,
    max_concurrent: int | None = None,
    usage_limit: int | None = None,
    is_active: bool | None = None,
    name: str | None = None,
) -> dict | None:
    """更新 Key 配置（并发上限、用量上限、启用状态）"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id FROM llm_key_pool WHERE id = ?", (key_id,)
        )
        if not await cursor.fetchone():
            return None

        sets: list[str] = []
        params: list = []

        if max_concurrent is not None:
            sets.append("max_concurrent = ?")
            params.append(max_concurrent)
        if usage_limit is not None:
            sets.append("usage_limit = ?")
            params.append(usage_limit)
        if is_active is not None:
            sets.append("is_active = ?")
            params.append(1 if is_active else 0)
        if name is not None:
            sets.append("name = ?")
            params.append(name)

        if not sets:
            return await get_llm_key(key_id)

        params.append(key_id)
        await conn.execute(
            f"UPDATE llm_key_pool SET {', '.join(sets)} WHERE id = ?",
            params,
        )
        await conn.commit()
        return await get_llm_key(key_id)
    finally:
        await conn.close()


async def delete_llm_key(key_id: str) -> bool:
    """删除 Key"""
    conn = await get_connection()
    try:
        # 先清理关联的 node_key_assignments
        await conn.execute(
            "DELETE FROM node_key_assignments WHERE key_id = ?", (key_id,)
        )
        cursor = await conn.execute(
            "DELETE FROM llm_key_pool WHERE id = ?", (key_id,)
        )
        await conn.commit()
        return cursor.rowcount > 0
    finally:
        await conn.close()


# ── Key 分配（最少连接数策略） ────────────────────────────────────

async def allocate_key(node_id: str, provider: str | None = None) -> dict | None:
    """为节点分配负载最低的 Key（最少连接数策略）

    Args:
        node_id: 节点 ID
        provider: 可选的提供商过滤

    Returns:
        分配结果 {"key_id", "provider", "api_key", "model"} 或 None（无可用 Key）
    """
    conn = await get_connection()
    try:
        # 先检查节点是否已有分配
        cursor = await conn.execute(
            """SELECT ka.key_id, kp.provider, kp.api_key_encrypted
               FROM node_key_assignments ka
               JOIN llm_key_pool kp ON ka.key_id = kp.id
               WHERE ka.node_id = ? AND kp.is_active = 1""",
            (node_id,),
        )
        existing = await cursor.fetchone()
        if existing:
            return {
                "key_id": existing[0],
                "provider": existing[1],
                "api_key": _decrypt_key(existing[2]),
            }

        # 查找可用 Key：启用、未满载
        query = """SELECT id, provider, api_key_encrypted, max_concurrent, current_concurrent
                   FROM llm_key_pool
                   WHERE is_active = 1 AND current_concurrent < max_concurrent"""
        params: list = []
        if provider:
            query += " AND provider = ?"
            params.append(provider)
        query += " ORDER BY current_concurrent ASC LIMIT 1"

        cursor = await conn.execute(query, params)
        row = await cursor.fetchone()
        if not row:
            return None

        key_id = row[0]
        now = datetime.now(timezone.utc).isoformat()

        # 创建分配记录
        assignment_id = str(uuid.uuid4())
        await conn.execute(
            """INSERT INTO node_key_assignments (id, node_id, key_id, assigned_at)
               VALUES (?, ?, ?, ?)""",
            (assignment_id, node_id, key_id, now),
        )
        # 递增 current_concurrent
        await conn.execute(
            "UPDATE llm_key_pool SET current_concurrent = current_concurrent + 1 WHERE id = ?",
            (key_id,),
        )
        await conn.commit()

        return {
            "key_id": key_id,
            "provider": row[1],
            "api_key": _decrypt_key(row[2]),
        }
    finally:
        await conn.close()
async def _reconcile_current_concurrent(conn) -> None:
    """根据 node_key_assignments 全量重算 current_concurrent，避免计数漂移"""
    cursor = await conn.execute("SELECT key_id FROM node_key_assignments")
    rows = await cursor.fetchall()
    counts = Counter(row[0] for row in rows)

    await conn.execute("UPDATE llm_key_pool SET current_concurrent = 0")
    for key_id, count in counts.items():
        await conn.execute(
            "UPDATE llm_key_pool SET current_concurrent = ? WHERE id = ?",
            (count, key_id),
        )


async def assign_key_to_node(
    node_id: str,
    key_id: str,
    replace_existing: bool = False,
) -> dict:
    """手动将指定 Key 分配给节点

    特性：
    - 幂等：同节点重复分配同一 key 不重复计数
    - 可替换：replace_existing=True 时替换旧 key
    - 并发安全：事务内完成 assignment 与计数更新
    """
    conn = await get_connection()
    try:
        await conn.execute("BEGIN IMMEDIATE")

        cursor = await conn.execute("SELECT id FROM nodes WHERE id = ?", (node_id,))
        if not await cursor.fetchone():
            raise KeyAssignmentNotFoundError("Node not found")

        cursor = await conn.execute(
            """SELECT id, provider, api_key_encrypted, max_concurrent,
                      current_concurrent, is_active
               FROM llm_key_pool WHERE id = ?""",
            (key_id,),
        )
        key_row = await cursor.fetchone()
        if not key_row:
            raise KeyAssignmentNotFoundError("LLM Key not found")
        if not key_row[5]:
            raise KeyAssignmentConflictError("LLM Key is inactive")

        cursor = await conn.execute(
            """SELECT id, key_id FROM node_key_assignments
               WHERE node_id = ? ORDER BY assigned_at DESC""",
            (node_id,),
        )
        existing_rows = await cursor.fetchall()

        latest_assignment_id = existing_rows[0][0] if existing_rows else None
        latest_key_id = existing_rows[0][1] if existing_rows else None

        if latest_key_id == key_id:
            if len(existing_rows) > 1:
                await conn.execute(
                    "DELETE FROM node_key_assignments WHERE node_id = ? AND id != ?",
                    (node_id, latest_assignment_id),
                )
                await _reconcile_current_concurrent(conn)
            await conn.commit()
            return {
                "node_id": node_id,
                "key_id": key_id,
                "provider": key_row[1],
                "replaced": False,
                "idempotent": True,
            }

        if latest_key_id and not replace_existing:
            raise KeyAssignmentConflictError("Node already has an assigned LLM Key")

        if key_row[4] >= key_row[3]:
            raise KeyAssignmentCapacityError("LLM Key capacity reached")

        if latest_key_id:
            await conn.execute("DELETE FROM node_key_assignments WHERE node_id = ?", (node_id,))

        assignment_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await conn.execute(
            """INSERT INTO node_key_assignments (id, node_id, key_id, assigned_at)
               VALUES (?, ?, ?, ?)""",
            (assignment_id, node_id, key_id, now),
        )

        if latest_key_id and latest_key_id != key_id:
            await conn.execute(
                """UPDATE llm_key_pool
                   SET current_concurrent = MAX(0, current_concurrent - 1)
                   WHERE id = ?""",
                (latest_key_id,),
            )

        await conn.execute(
            "UPDATE llm_key_pool SET current_concurrent = current_concurrent + 1 WHERE id = ?",
            (key_id,),
        )

        await _reconcile_current_concurrent(conn)
        await conn.commit()

        return {
            "node_id": node_id,
            "key_id": key_id,
            "provider": key_row[1],
            "replaced": bool(latest_key_id and latest_key_id != key_id),
            "idempotent": False,
        }
    except Exception:
        await conn.rollback()
        raise
    finally:
        await conn.close()


# ── 辅助函数 ──────────────────────────────────────────────────────

def _row_to_key(row) -> dict:
    """将数据库行转换为 Key 字典（隐藏实际 Key 值）"""
    decrypted = _decrypt_key(row[3])
    return {
        "id": row[0],
        "name": row[1],
        "provider": row[2],
        "api_key_preview": _mask_key(decrypted),
        "max_concurrent": row[4],
        "current_concurrent": row[5],
        "usage_limit": row[6],
        "total_usage": row[7],
        "is_active": bool(row[8]),
        "created_at": row[9],
    }


# ── 限流处理与 Key 切换 ──────────────────────────────────────────

async def handle_ratelimit(node_id: str, key_id: str) -> dict | None:
    """处理限流事件，将节点切换到其他可用 Key

    Args:
        node_id: 节点 ID
        key_id: 被限流的 Key ID

    Returns:
        新分配结果或 None（无其他可用 Key）
    """
    conn = await get_connection()
    try:
        # 移除当前分配
        await conn.execute(
            "DELETE FROM node_key_assignments WHERE node_id = ? AND key_id = ?",
            (node_id, key_id),
        )
        # 递减旧 Key 的 current_concurrent
        await conn.execute(
            """UPDATE llm_key_pool SET current_concurrent = MAX(0, current_concurrent - 1)
               WHERE id = ?""",
            (key_id,),
        )
        await conn.commit()
    finally:
        await conn.close()

    # 重新分配，排除被限流的 Key
    return await _allocate_key_excluding(node_id, exclude_key_id=key_id)


async def _allocate_key_excluding(
    node_id: str, exclude_key_id: str | None = None
) -> dict | None:
    """为节点分配 Key，可排除指定 Key"""
    conn = await get_connection()
    try:
        query = """SELECT id, provider, api_key_encrypted, max_concurrent, current_concurrent
                   FROM llm_key_pool
                   WHERE is_active = 1 AND current_concurrent < max_concurrent"""
        params: list = []
        if exclude_key_id:
            query += " AND id != ?"
            params.append(exclude_key_id)
        query += " ORDER BY current_concurrent ASC LIMIT 1"

        cursor = await conn.execute(query, params)
        row = await cursor.fetchone()
        if not row:
            return None

        key_id = row[0]
        now = datetime.now(timezone.utc).isoformat()

        assignment_id = str(uuid.uuid4())
        await conn.execute(
            """INSERT INTO node_key_assignments (id, node_id, key_id, assigned_at)
               VALUES (?, ?, ?, ?)""",
            (assignment_id, node_id, key_id, now),
        )
        await conn.execute(
            "UPDATE llm_key_pool SET current_concurrent = current_concurrent + 1 WHERE id = ?",
            (key_id,),
        )
        await conn.commit()

        return {
            "key_id": key_id,
            "provider": row[1],
            "api_key": _decrypt_key(row[2]),
        }
    finally:
        await conn.close()


async def check_usage_limits() -> list[str]:
    """检查所有 Key 的用量是否超限，超限则禁用并触发批量切换

    Returns:
        被禁用的 Key ID 列表
    """
    conn = await get_connection()
    disabled_keys: list[str] = []
    try:
        # 查找超限的 Key（usage_limit > 0 且 total_usage >= usage_limit）
        cursor = await conn.execute(
            """SELECT id FROM llm_key_pool
               WHERE is_active = 1 AND usage_limit > 0 AND total_usage >= usage_limit"""
        )
        rows = await cursor.fetchall()
        disabled_keys = [row[0] for row in rows]

        if not disabled_keys:
            return []

        # 禁用超限 Key
        placeholders = ",".join("?" for _ in disabled_keys)
        await conn.execute(
            f"UPDATE llm_key_pool SET is_active = 0 WHERE id IN ({placeholders})",
            disabled_keys,
        )
        await conn.commit()
    finally:
        await conn.close()

    # 为受影响的节点重新分配 Key
    for key_id in disabled_keys:
        await _reassign_nodes_from_key(key_id)

    return disabled_keys


async def _reassign_nodes_from_key(key_id: str) -> None:
    """将使用指定 Key 的所有节点重新分配到其他可用 Key"""
    conn = await get_connection()
    try:
        # 查找使用该 Key 的节点
        cursor = await conn.execute(
            "SELECT node_id FROM node_key_assignments WHERE key_id = ?",
            (key_id,),
        )
        rows = await cursor.fetchall()
        node_ids = [row[0] for row in rows]

        if not node_ids:
            return

        # 移除旧分配
        await conn.execute(
            "DELETE FROM node_key_assignments WHERE key_id = ?", (key_id,)
        )
        # 重置 current_concurrent
        await conn.execute(
            "UPDATE llm_key_pool SET current_concurrent = 0 WHERE id = ?",
            (key_id,),
        )
        await conn.commit()
    finally:
        await conn.close()

    # 为每个节点重新分配
    for nid in node_ids:
        await allocate_key(nid)


# ── Token 用量存储 ────────────────────────────────────────────────

async def store_token_usage(node_id: str, records: list[dict]) -> int:
    """存储 Token 用量记录并更新 Key 累计用量

    Args:
        node_id: 节点 ID
        records: 用量记录列表

    Returns:
        成功存储的记录数
    """
    if not records:
        return 0

    conn = await get_connection()
    now = datetime.now(timezone.utc).isoformat()
    stored = 0
    try:
        for rec in records:
            record_id = str(uuid.uuid4())
            total = rec.get("total_tokens", 0)
            key_id = rec.get("key_id", "")

            await conn.execute(
                """INSERT INTO token_usage
                   (id, node_id, key_id, model, prompt_tokens, completion_tokens,
                    total_tokens, timestamp, received_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record_id, node_id, key_id,
                    rec.get("model", ""),
                    rec.get("prompt_tokens", 0),
                    rec.get("completion_tokens", 0),
                    total,
                    rec.get("timestamp", now),
                    now,
                ),
            )

            # 更新 Key 累计用量
            if key_id:
                await conn.execute(
                    "UPDATE llm_key_pool SET total_usage = total_usage + ? WHERE id = ?",
                    (total, key_id),
                )
            stored += 1

        await conn.commit()
    finally:
        await conn.close()

    return stored



# ── Token 用量查询 ────────────────────────────────────────────────

async def query_token_usage(
    node_id: str | None = None,
    key_id: str | None = None,
    model: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """查询 Token 用量记录，支持多维度过滤"""
    conn = await get_connection()
    try:
        query = """SELECT id, node_id, key_id, model, prompt_tokens,
                          completion_tokens, total_tokens, timestamp, received_at
                   FROM token_usage WHERE 1=1"""
        params: list = []

        if node_id:
            query += " AND node_id = ?"
            params.append(node_id)
        if key_id:
            query += " AND key_id = ?"
            params.append(key_id)
        if model:
            query += " AND model = ?"
            params.append(model)
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        return [
            {
                "id": r[0], "node_id": r[1], "key_id": r[2], "model": r[3],
                "prompt_tokens": r[4], "completion_tokens": r[5],
                "total_tokens": r[6], "timestamp": r[7], "received_at": r[8],
            }
            for r in rows
        ]
    finally:
        await conn.close()


async def get_usage_summary(
    node_id: str | None = None,
    key_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict:
    """获取 Token 用量汇总"""
    conn = await get_connection()
    try:
        query = """SELECT COALESCE(SUM(prompt_tokens), 0),
                          COALESCE(SUM(completion_tokens), 0),
                          COALESCE(SUM(total_tokens), 0),
                          COUNT(*)
                   FROM token_usage WHERE 1=1"""
        params: list = []

        if node_id:
            query += " AND node_id = ?"
            params.append(node_id)
        if key_id:
            query += " AND key_id = ?"
            params.append(key_id)
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)

        cursor = await conn.execute(query, params)
        row = await cursor.fetchone()
        return {
            "total_prompt_tokens": row[0],
            "total_completion_tokens": row[1],
            "total_tokens": row[2],
            "record_count": row[3],
        }
    finally:
        await conn.close()

async def get_usage_by_node(
    key_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict]:
    """按节点汇总 Token 用量"""
    conn = await get_connection()
    try:
        query = """SELECT tu.node_id, n.hostname,
                          COALESCE(SUM(tu.prompt_tokens), 0),
                          COALESCE(SUM(tu.completion_tokens), 0),
                          COALESCE(SUM(tu.total_tokens), 0),
                          COUNT(*)
                   FROM token_usage tu
                   LEFT JOIN nodes n ON tu.node_id = n.id
                   WHERE 1=1"""
        params: list = []
        if key_id:
            query += " AND tu.key_id = ?"
            params.append(key_id)
        if start_time:
            query += " AND tu.timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND tu.timestamp <= ?"
            params.append(end_time)
        query += " GROUP BY tu.node_id ORDER BY SUM(tu.total_tokens) DESC"

        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        return [
            {
                "node_id": r[0],
                "hostname": r[1] or r[0][:8],
                "prompt_tokens": r[2],
                "completion_tokens": r[3],
                "total_tokens": r[4],
                "record_count": r[5],
            }
            for r in rows
        ]
    finally:
        await conn.close()



