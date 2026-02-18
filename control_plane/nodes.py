"""节点管理逻辑 - 注册令牌、节点注册、心跳处理、离线检测"""

import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from control_plane.database import get_connection


# ── 注册令牌 ──────────────────────────────────────────────────────

async def create_registration_token(user_id: str, expires_hours: int = 24) -> dict:
    """生成注册令牌，绑定用户，默认 24 小时有效期"""
    conn = await get_connection()
    try:
        token_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(hours=expires_hours)).isoformat()

        await conn.execute(
            """INSERT INTO registration_tokens (id, user_id, is_used, expires_at, created_at)
               VALUES (?, ?, 0, ?, ?)""",
            (token_id, user_id, expires_at, now.isoformat()),
        )
        await conn.commit()

        return {
            "id": token_id,
            "user_id": user_id,
            "is_used": False,
            "expires_at": expires_at,
            "created_at": now.isoformat(),
        }
    finally:
        await conn.close()


async def validate_registration_token(token_id: str) -> dict | None:
    """验证注册令牌：存在、未使用、未过期。返回令牌记录或 None"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, user_id, is_used, expires_at, created_at "
            "FROM registration_tokens WHERE id = ?",
            (token_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        token = {
            "id": row[0],
            "user_id": row[1],
            "is_used": bool(row[2]),
            "expires_at": row[3],
            "created_at": row[4],
        }

        # 已使用
        if token["is_used"]:
            return None

        # 已过期
        expires_at = datetime.fromisoformat(token["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_at:
            return None

        return token
    finally:
        await conn.close()


async def mark_token_used(token_id: str) -> None:
    """将注册令牌标记为已使用"""
    conn = await get_connection()
    try:
        await conn.execute(
            "UPDATE registration_tokens SET is_used = 1 WHERE id = ?",
            (token_id,),
        )
        await conn.commit()
    finally:
        await conn.close()


# ── 节点注册 ──────────────────────────────────────────────────────

async def register_node(token_id: str, hostname: str) -> dict:
    """使用注册令牌注册节点

    验证令牌有效性，创建节点记录，标记令牌已使用，返回 node_id 和 api_key。

    Raises:
        ValueError: 令牌无效、已使用或已过期
    """
    token = await validate_registration_token(token_id)
    if not token:
        raise ValueError("Invalid, expired, or already used registration token")

    node_id = str(uuid.uuid4())
    api_key = secrets.token_urlsafe(48)
    # 存储 API Key 的哈希（使用简单的 SHA-256，因为 API Key 本身是高熵随机值）
    import hashlib
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    now = datetime.now(timezone.utc).isoformat()

    conn = await get_connection()
    try:
        await conn.execute(
            """INSERT INTO nodes (id, user_id, hostname, api_key_hash, status, last_heartbeat,
                                  config_version, policy_version, created_at)
               VALUES (?, ?, ?, ?, 'offline', NULL, 0, 0, ?)""",
            (node_id, token["user_id"], hostname, api_key_hash, now),
        )
        # 标记令牌已使用
        await conn.execute(
            "UPDATE registration_tokens SET is_used = 1 WHERE id = ?",
            (token_id,),
        )
        await conn.commit()

        return {"node_id": node_id, "api_key": api_key}
    finally:
        await conn.close()


async def verify_node_api_key(node_id: str, api_key: str) -> dict | None:
    """验证节点 API Key，返回节点记录或 None"""
    import hashlib
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, user_id, hostname, api_key_hash, status, last_heartbeat, "
            "config_version, policy_version, last_report, created_at "
            "FROM nodes WHERE id = ? AND api_key_hash = ?",
            (node_id, api_key_hash),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return _row_to_node(row)
    finally:
        await conn.close()


# ── 心跳处理 ──────────────────────────────────────────────────────

async def process_heartbeat(node_id: str, status_data: dict) -> dict:
    """处理心跳上报

    更新 last_heartbeat 和 last_report，检查策略/配置版本，返回更新标志。
    同时清理该节点的过期任务锁。

    Returns:
        HeartbeatResponse 字典
    """
    # 清理过期任务锁
    from control_plane.tasks import cleanup_expired_locks
    await cleanup_expired_locks()

    now = datetime.now(timezone.utc).isoformat()
    report_json = json.dumps(status_data, ensure_ascii=False)

    conn = await get_connection()
    try:
        # 更新节点心跳时间和状态
        await conn.execute(
            """UPDATE nodes SET last_heartbeat = ?, status = 'online', last_report = ?
               WHERE id = ?""",
            (now, report_json, node_id),
        )
        await conn.commit()

        # 获取节点当前的策略和配置版本
        cursor = await conn.execute(
            "SELECT config_version, policy_version FROM nodes WHERE id = ?",
            (node_id,),
        )
        node_row = await cursor.fetchone()
        if not node_row:
            return {
                "has_policy_update": False,
                "has_config_update": False,
                "latest_policy_version": 0,
                "latest_config_version": 0,
                "has_skill_update": False,
            }

        # 查询 Control Plane 端的最新策略版本
        latest_policy_version = 0
        cursor = await conn.execute(
            "SELECT version FROM resource_policies WHERE node_id = ?",
            (node_id,),
        )
        policy_row = await cursor.fetchone()
        if policy_row:
            latest_policy_version = policy_row[0]

        # 查询 Control Plane 端的最新配置版本
        latest_config_version = 0
        cursor = await conn.execute(
            "SELECT version FROM node_configs WHERE node_id = ?",
            (node_id,),
        )
        config_row = await cursor.fetchone()
        if config_row:
            latest_config_version = config_row[0]

        # 比较 Agent 上报的版本与 CP 端最新版本
        agent_policy_version = status_data.get("policy_version", 0)
        agent_config_version = status_data.get("config_version", 0)

        return {
            "has_policy_update": latest_policy_version > agent_policy_version,
            "has_config_update": latest_config_version > agent_config_version,
            "latest_policy_version": latest_policy_version,
            "latest_config_version": latest_config_version,
            "has_skill_update": latest_policy_version > agent_policy_version,
        }
    finally:
        await conn.close()


# ── 离线检测 ──────────────────────────────────────────────────────

async def detect_offline_nodes(heartbeat_interval_s: int = 30) -> list[str]:
    """检测离线节点：连续 3 次心跳间隔未收到心跳则标记离线

    Returns:
        被标记为离线的节点 ID 列表
    """
    threshold_seconds = heartbeat_interval_s * 3
    cutoff = (
        datetime.now(timezone.utc) - timedelta(seconds=threshold_seconds)
    ).isoformat()

    conn = await get_connection()
    try:
        # 查找超时的在线节点
        cursor = await conn.execute(
            "SELECT id FROM nodes WHERE status = 'online' AND last_heartbeat < ?",
            (cutoff,),
        )
        rows = await cursor.fetchall()
        offline_ids = [row[0] for row in rows]

        if offline_ids:
            placeholders = ",".join("?" for _ in offline_ids)
            await conn.execute(
                f"UPDATE nodes SET status = 'offline' WHERE id IN ({placeholders})",
                offline_ids,
            )
            await conn.commit()

        return offline_ids
    finally:
        await conn.close()


# ── 节点查询 ──────────────────────────────────────────────────────

async def get_node_by_id(node_id: str) -> dict | None:
    """根据 ID 查询节点"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, user_id, hostname, api_key_hash, status, last_heartbeat, "
            "config_version, policy_version, last_report, created_at "
            "FROM nodes WHERE id = ?",
            (node_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return _row_to_node(row)
    finally:
        await conn.close()


async def list_nodes(user_id: str | None = None) -> list[dict]:
    """列出节点，可选按用户过滤"""
    conn = await get_connection()
    try:
        if user_id:
            cursor = await conn.execute(
                "SELECT id, user_id, hostname, api_key_hash, status, last_heartbeat, "
                "config_version, policy_version, last_report, created_at "
                "FROM nodes WHERE user_id = ? ORDER BY created_at",
                (user_id,),
            )
        else:
            cursor = await conn.execute(
                "SELECT id, user_id, hostname, api_key_hash, status, last_heartbeat, "
                "config_version, policy_version, last_report, created_at "
                "FROM nodes ORDER BY created_at"
            )
        rows = await cursor.fetchall()
        return [_row_to_node(row) for row in rows]
    finally:
        await conn.close()


async def delete_node(node_id: str) -> bool:
    """删除节点，返回是否成功"""
    conn = await get_connection()
    try:
        cursor = await conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
        await conn.commit()
        return cursor.rowcount > 0
    finally:
        await conn.close()


# ── 辅助函数 ──────────────────────────────────────────────────────

def _row_to_node(row) -> dict:
    """将数据库行转换为节点字典"""
    last_report = row[8]
    if isinstance(last_report, str):
        try:
            last_report = json.loads(last_report)
        except (json.JSONDecodeError, TypeError):
            last_report = None

    return {
        "id": row[0],
        "user_id": row[1],
        "hostname": row[2],
        "status": row[4],
        "last_heartbeat": row[5],
        "config_version": row[6],
        "policy_version": row[7],
        "last_report": last_report,
        "created_at": row[9],
    }
