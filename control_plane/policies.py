"""策略管理逻辑 - Skill 注册表、MCP Server 注册表、节点资源策略 CRUD"""

import json
import uuid
from datetime import datetime, timezone

from control_plane.database import get_connection


# ── Skill 注册表 CRUD ─────────────────────────────────────────────

async def create_skill(name: str, description: str = "", source: str = "custom") -> dict:
    """注册新 Skill 到全局注册表"""
    conn = await get_connection()
    try:
        # 检查名称唯一性
        cursor = await conn.execute(
            "SELECT id FROM skill_registry WHERE name = ?", (name,)
        )
        if await cursor.fetchone():
            raise ValueError(f"Skill '{name}' already exists")

        skill_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        await conn.execute(
            """INSERT INTO skill_registry (id, name, description, source, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (skill_id, name, description, source, now),
        )
        await conn.commit()

        return {
            "id": skill_id,
            "name": name,
            "description": description,
            "source": source,
            "version": 1,
            "checksum": "",
            "file_size": 0,
            "created_at": now,
        }
    finally:
        await conn.close()


async def list_skills() -> list[dict]:
    """列出全局 Skill 注册表中的所有 Skill"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, name, description, source, version, checksum, file_size, created_at "
            "FROM skill_registry ORDER BY created_at"
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "source": row[3],
                "version": row[4],
                "checksum": row[5],
                "file_size": row[6],
                "created_at": row[7],
            }
            for row in rows
        ]
    finally:
        await conn.close()


async def get_skill_by_name(name: str) -> dict | None:
    """根据名称查询 Skill"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, name, description, source, version, checksum, file_size, created_at "
            "FROM skill_registry WHERE name = ?",
            (name,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "source": row[3],
            "version": row[4],
            "checksum": row[5],
            "file_size": row[6],
            "created_at": row[7],
        }
    finally:
        await conn.close()


# ── MCP Server 注册表 CRUD ────────────────────────────────────────

async def create_mcp_server(
    name: str,
    connection_type: str = "stdio",
    config: dict | None = None,
    description: str = "",
) -> dict:
    """注册新 MCP Server 到全局注册表"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id FROM mcp_server_registry WHERE name = ?", (name,)
        )
        if await cursor.fetchone():
            raise ValueError(f"MCP Server '{name}' already exists")

        server_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        config_json = json.dumps(config or {}, ensure_ascii=False)

        await conn.execute(
            """INSERT INTO mcp_server_registry (id, name, connection_type, config, description, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (server_id, name, connection_type, config_json, description, now),
        )
        await conn.commit()

        return {
            "id": server_id,
            "name": name,
            "connection_type": connection_type,
            "config": config or {},
            "description": description,
            "created_at": now,
        }
    finally:
        await conn.close()


async def list_mcp_servers() -> list[dict]:
    """列出全局 MCP Server 注册表"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, name, connection_type, config, description, created_at "
            "FROM mcp_server_registry ORDER BY created_at"
        )
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            config = row[3]
            if isinstance(config, str):
                try:
                    config = json.loads(config)
                except (json.JSONDecodeError, TypeError):
                    config = {}
            result.append({
                "id": row[0],
                "name": row[1],
                "connection_type": row[2],
                "config": config,
                "description": row[4],
                "created_at": row[5],
            })
        return result
    finally:
        await conn.close()


async def get_mcp_server_by_name(name: str) -> dict | None:
    """根据名称查询 MCP Server"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, name, connection_type, config, description, created_at "
            "FROM mcp_server_registry WHERE name = ?",
            (name,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        config = row[3]
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except (json.JSONDecodeError, TypeError):
                config = {}
        return {
            "id": row[0],
            "name": row[1],
            "connection_type": row[2],
            "config": config,
            "description": row[4],
            "created_at": row[5],
        }
    finally:
        await conn.close()


# ── 节点资源策略 CRUD ─────────────────────────────────────────────

async def get_node_policy(node_id: str) -> dict | None:
    """获取节点的资源策略，如果不存在则自动创建空策略"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, node_id, allowed_skills, allowed_mcp_servers, version, updated_at "
            "FROM resource_policies WHERE node_id = ?",
            (node_id,),
        )
        row = await cursor.fetchone()

        if not row:
            # 策略不存在，检查节点是否存在
            cursor = await conn.execute("SELECT id FROM nodes WHERE id = ?", (node_id,))
            if not await cursor.fetchone():
                return None

            # 节点存在但无策略，自动创建空策略
            policy_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            await conn.execute(
                """INSERT INTO resource_policies (id, node_id, allowed_skills, allowed_mcp_servers, version, updated_at)
                   VALUES (?, ?, '[]', '[]', 1, ?)""",
                (policy_id, node_id, now),
            )
            await conn.execute(
                "UPDATE nodes SET policy_version = 1 WHERE id = ?",
                (node_id,),
            )
            await conn.commit()
            return {
                "id": policy_id,
                "node_id": node_id,
                "allowed_skills": [],
                "allowed_mcp_servers": [],
                "version": 1,
                "updated_at": now,
                "skill_versions": {},
            }

        policy = _row_to_policy(row)

        # 查询策略中 Skill 的版本信息
        allowed_skills = policy["allowed_skills"]
        if allowed_skills:
            placeholders = ",".join("?" for _ in allowed_skills)
            cursor = await conn.execute(
                f"SELECT name, version, checksum FROM skill_registry WHERE name IN ({placeholders})",
                allowed_skills,
            )
            skill_rows = await cursor.fetchall()
            policy["skill_versions"] = {
                r[0]: {"version": r[1], "checksum": r[2]} for r in skill_rows
            }
        else:
            policy["skill_versions"] = {}

        return policy
    finally:
        await conn.close()


async def update_node_policy(
    node_id: str,
    allowed_skills: list[str],
    allowed_mcp_servers: list[str],
) -> dict:
    """更新节点资源策略，版本号自动递增

    如果策略不存在则创建，存在则更新并递增版本号。
    同时更新 nodes 表中的 policy_version。
    """
    now = datetime.now(timezone.utc).isoformat()
    skills_json = json.dumps(allowed_skills, ensure_ascii=False)
    servers_json = json.dumps(allowed_mcp_servers, ensure_ascii=False)

    conn = await get_connection()
    try:
        # 检查节点是否存在
        cursor = await conn.execute("SELECT id FROM nodes WHERE id = ?", (node_id,))
        if not await cursor.fetchone():
            raise ValueError(f"Node '{node_id}' not found")

        # 检查是否已有策略
        cursor = await conn.execute(
            "SELECT id, version FROM resource_policies WHERE node_id = ?",
            (node_id,),
        )
        existing = await cursor.fetchone()

        if existing:
            new_version = existing[1] + 1
            await conn.execute(
                """UPDATE resource_policies
                   SET allowed_skills = ?, allowed_mcp_servers = ?, version = ?, updated_at = ?
                   WHERE node_id = ?""",
                (skills_json, servers_json, new_version, now, node_id),
            )
            policy_id = existing[0]
        else:
            policy_id = str(uuid.uuid4())
            new_version = 1
            await conn.execute(
                """INSERT INTO resource_policies (id, node_id, allowed_skills, allowed_mcp_servers, version, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (policy_id, node_id, skills_json, servers_json, new_version, now),
            )

        # 同步更新 nodes 表的 policy_version
        await conn.execute(
            "UPDATE nodes SET policy_version = ? WHERE id = ?",
            (new_version, node_id),
        )
        await conn.commit()

        return {
            "id": policy_id,
            "node_id": node_id,
            "allowed_skills": allowed_skills,
            "allowed_mcp_servers": allowed_mcp_servers,
            "version": new_version,
            "updated_at": now,
        }
    finally:
        await conn.close()


# ── 辅助函数 ──────────────────────────────────────────────────────

def _row_to_policy(row) -> dict:
    """将数据库行转换为策略字典"""
    allowed_skills = row[2]
    if isinstance(allowed_skills, str):
        try:
            allowed_skills = json.loads(allowed_skills)
        except (json.JSONDecodeError, TypeError):
            allowed_skills = []

    allowed_mcp_servers = row[3]
    if isinstance(allowed_mcp_servers, str):
        try:
            allowed_mcp_servers = json.loads(allowed_mcp_servers)
        except (json.JSONDecodeError, TypeError):
            allowed_mcp_servers = []

    return {
        "id": row[0],
        "node_id": row[1],
        "allowed_skills": allowed_skills,
        "allowed_mcp_servers": allowed_mcp_servers,
        "version": row[4],
        "updated_at": row[5],
    }
