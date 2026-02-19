"""配置管理逻辑 - 节点配置存储和版本管理"""

import json
import uuid
from datetime import datetime, timezone

from control_plane.database import get_connection


async def get_node_config(node_id: str) -> dict | None:
    """获取节点配置，如果不存在则自动创建空配置"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, node_id, config_data, version, updated_at "
            "FROM node_configs WHERE node_id = ?",
            (node_id,),
        )
        row = await cursor.fetchone()
        if row:
            return _row_to_config(row)

        # 配置不存在，检查节点是否存在
        cursor = await conn.execute("SELECT id FROM nodes WHERE id = ?", (node_id,))
        if not await cursor.fetchone():
            return None

        # 节点存在但无配置，自动创建空配置
        config_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await conn.execute(
            """INSERT INTO node_configs (id, node_id, config_data, version, updated_at)
               VALUES (?, ?, '{}', 1, ?)""",
            (config_id, node_id, now),
        )
        await conn.execute(
            "UPDATE nodes SET config_version = 1 WHERE id = ?",
            (node_id,),
        )
        await conn.commit()
        return {
            "id": config_id,
            "node_id": node_id,
            "config_data": {},
            "version": 1,
            "updated_at": now,
        }
    finally:
        await conn.close()


async def update_node_config(node_id: str, config_data: dict) -> dict:
    """更新节点配置，版本号自动递增

    如果配置不存在则创建，存在则更新并递增版本号。
    同时更新 nodes 表中的 config_version。
    """
    now = datetime.now(timezone.utc).isoformat()
    config_json = json.dumps(config_data, ensure_ascii=False)

    conn = await get_connection()
    try:
        # 检查节点是否存在
        cursor = await conn.execute("SELECT id FROM nodes WHERE id = ?", (node_id,))
        if not await cursor.fetchone():
            raise ValueError(f"Node '{node_id}' not found")

        # 检查是否已有配置
        cursor = await conn.execute(
            "SELECT id, version FROM node_configs WHERE node_id = ?",
            (node_id,),
        )
        existing = await cursor.fetchone()

        if existing:
            new_version = existing[1] + 1
            await conn.execute(
                """UPDATE node_configs
                   SET config_data = ?, version = ?, updated_at = ?
                   WHERE node_id = ?""",
                (config_json, new_version, now, node_id),
            )
            config_id = existing[0]
        else:
            config_id = str(uuid.uuid4())
            new_version = 1
            await conn.execute(
                """INSERT INTO node_configs (id, node_id, config_data, version, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (config_id, node_id, config_json, new_version, now),
            )

        # 同步更新 nodes 表的 config_version
        await conn.execute(
            "UPDATE nodes SET config_version = ? WHERE id = ?",
            (new_version, node_id),
        )
        await conn.commit()

        return {
            "id": config_id,
            "node_id": node_id,
            "config_data": config_data,
            "version": new_version,
            "updated_at": now,
        }
    finally:
        await conn.close()


# ── 辅助函数 ──────────────────────────────────────────────────────

def _row_to_config(row) -> dict:
    """将数据库行转换为配置字典"""
    config_data = row[2]
    if isinstance(config_data, str):
        try:
            config_data = json.loads(config_data)
        except (json.JSONDecodeError, TypeError):
            config_data = {}

    return {
        "id": row[0],
        "node_id": row[1],
        "config_data": config_data,
        "version": row[3],
        "updated_at": row[4],
    }


async def get_node_config_with_llm_key(node_id: str) -> dict | None:
    """获取节点配置，自动注入分配的 LLM Key 信息"""
    config = await get_node_config(node_id)
    if not config:
        return None

    # 查询节点分配的 LLM Key
    from control_plane.llm_keys import allocate_key, _decrypt_key
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            """SELECT ka.key_id, kp.provider, kp.api_key_encrypted
               FROM node_key_assignments ka
               JOIN llm_key_pool kp ON ka.key_id = kp.id
               WHERE ka.node_id = ? AND kp.is_active = 1""",
            (node_id,),
        )
        row = await cursor.fetchone()
        if row:
            config_data = config.get("config_data", {})
            config_data["llm_key"] = {
                "key_id": row[0],
                "provider": row[1],
                "api_key": _decrypt_key(row[2]),
            }
            config["config_data"] = config_data
    finally:
        await conn.close()

    return config

