"""Persona 管理逻辑 — 人格注册、记忆存储和跨节点记忆合并"""

import json
import uuid
from datetime import datetime, timezone

from control_plane.database import get_connection


# ── Persona CRUD ──────────────────────────────────────────────────

async def create_persona(
    name: str,
    persona_content: str,
    description: str = "",
    max_memory_chars: int = 50000,
) -> dict:
    """创建人格定义"""
    persona_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    conn = await get_connection()
    try:
        await conn.execute(
            """INSERT INTO persona_registry
               (id, name, description, persona_content, version, max_memory_chars, created_at, updated_at)
               VALUES (?, ?, ?, ?, 1, ?, ?, ?)""",
            (persona_id, name, description, persona_content, max_memory_chars, now, now),
        )
        await conn.commit()
        return {
            "id": persona_id,
            "name": name,
            "description": description,
            "persona_content": persona_content,
            "version": 1,
            "max_memory_chars": max_memory_chars,
            "created_at": now,
            "updated_at": now,
        }
    finally:
        await conn.close()


async def update_persona(
    persona_id: str,
    persona_content: str | None = None,
    description: str | None = None,
    max_memory_chars: int | None = None,
) -> dict | None:
    """更新人格定义（版本号自动递增，人格内容变更时）"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, name, description, persona_content, version, max_memory_chars, created_at, updated_at "
            "FROM persona_registry WHERE id = ?",
            (persona_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        current = _row_to_persona(row)
        now = datetime.now(timezone.utc).isoformat()
        new_content = persona_content if persona_content is not None else current["persona_content"]
        new_desc = description if description is not None else current["description"]
        new_max = max_memory_chars if max_memory_chars is not None else current["max_memory_chars"]

        # 人格内容变更时递增版本号
        new_version = current["version"]
        if persona_content is not None and persona_content != current["persona_content"]:
            new_version += 1

        await conn.execute(
            """UPDATE persona_registry
               SET persona_content = ?, description = ?, max_memory_chars = ?,
                   version = ?, updated_at = ?
               WHERE id = ?""",
            (new_content, new_desc, new_max, new_version, now, persona_id),
        )
        await conn.commit()

        current.update({
            "persona_content": new_content,
            "description": new_desc,
            "max_memory_chars": new_max,
            "version": new_version,
            "updated_at": now,
        })
        return current
    finally:
        await conn.close()


async def get_persona(persona_id: str) -> dict | None:
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, name, description, persona_content, version, max_memory_chars, created_at, updated_at "
            "FROM persona_registry WHERE id = ?",
            (persona_id,),
        )
        row = await cursor.fetchone()
        return _row_to_persona(row) if row else None
    finally:
        await conn.close()


async def get_persona_by_name(name: str) -> dict | None:
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, name, description, persona_content, version, max_memory_chars, created_at, updated_at "
            "FROM persona_registry WHERE name = ?",
            (name,),
        )
        row = await cursor.fetchone()
        return _row_to_persona(row) if row else None
    finally:
        await conn.close()


async def list_personas() -> list[dict]:
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, name, description, persona_content, version, max_memory_chars, created_at, updated_at "
            "FROM persona_registry ORDER BY created_at"
        )
        rows = await cursor.fetchall()
        return [_row_to_persona(r) for r in rows]
    finally:
        await conn.close()


async def delete_persona(persona_id: str) -> bool:
    conn = await get_connection()
    try:
        cursor = await conn.execute("DELETE FROM persona_registry WHERE id = ?", (persona_id,))
        await conn.commit()
        return cursor.rowcount > 0
    finally:
        await conn.close()


# ── 节点记忆上报与查询 ────────────────────────────────────────────

async def upload_node_memory(
    persona_id: str,
    node_id: str,
    memory_content: str,
    history_entries: str = "",
) -> dict:
    """节点上报某个 persona 的记忆增量

    采用 upsert 模式：存在则更新，不存在则创建。
    记忆内容受 max_memory_chars 限制，超出时截断旧内容。
    """
    now = datetime.now(timezone.utc).isoformat()

    conn = await get_connection()
    try:
        # 获取 persona 的记忆上限
        cursor = await conn.execute(
            "SELECT max_memory_chars FROM persona_registry WHERE id = ?",
            (persona_id,),
        )
        persona_row = await cursor.fetchone()
        if not persona_row:
            raise ValueError(f"Persona '{persona_id}' not found")
        max_chars = persona_row[0]

        # 截断记忆防止膨胀
        if len(memory_content) > max_chars:
            memory_content = memory_content[-max_chars:]

        # upsert
        cursor = await conn.execute(
            "SELECT id, memory_version, history_content FROM persona_memory WHERE persona_id = ? AND node_id = ?",
            (persona_id, node_id),
        )
        existing = await cursor.fetchone()

        if existing:
            new_version = existing[1] + 1
            # 追加历史条目
            old_history = existing[2] or ""
            combined_history = old_history + ("\n\n" if old_history else "") + history_entries if history_entries else old_history
            # 历史也限制大小
            if len(combined_history) > max_chars:
                combined_history = combined_history[-max_chars:]

            await conn.execute(
                """UPDATE persona_memory
                   SET memory_content = ?, history_content = ?, memory_version = ?, updated_at = ?
                   WHERE persona_id = ? AND node_id = ?""",
                (memory_content, combined_history, new_version, now, persona_id, node_id),
            )
            memory_id = existing[0]
        else:
            memory_id = str(uuid.uuid4())
            new_version = 1
            await conn.execute(
                """INSERT INTO persona_memory
                   (id, persona_id, node_id, memory_content, history_content, memory_version, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (memory_id, persona_id, node_id, memory_content, history_entries or "", new_version, now),
            )

        await conn.commit()
        return {
            "id": memory_id,
            "persona_id": persona_id,
            "node_id": node_id,
            "memory_version": new_version,
            "updated_at": now,
        }
    finally:
        await conn.close()


async def get_node_memory(persona_id: str, node_id: str) -> dict | None:
    """获取某节点某 persona 的记忆"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, persona_id, node_id, memory_content, history_content, memory_version, updated_at "
            "FROM persona_memory WHERE persona_id = ? AND node_id = ?",
            (persona_id, node_id),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0], "persona_id": row[1], "node_id": row[2],
            "memory_content": row[3], "history_content": row[4],
            "memory_version": row[5], "updated_at": row[6],
        }
    finally:
        await conn.close()


async def get_all_node_memories(persona_id: str) -> list[dict]:
    """获取某 persona 在所有节点上的记忆（用于合并）"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, persona_id, node_id, memory_content, history_content, memory_version, updated_at "
            "FROM persona_memory WHERE persona_id = ? ORDER BY updated_at DESC",
            (persona_id,),
        )
        rows = await cursor.fetchall()
        return [
            {"id": r[0], "persona_id": r[1], "node_id": r[2],
             "memory_content": r[3], "history_content": r[4],
             "memory_version": r[5], "updated_at": r[6]}
            for r in rows
        ]
    finally:
        await conn.close()


# ── 全局记忆合并 ──────────────────────────────────────────────────

async def get_global_memory(persona_id: str) -> dict | None:
    """获取 persona 的全局合并记忆"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, persona_id, memory_content, merge_version, updated_at "
            "FROM persona_global_memory WHERE persona_id = ?",
            (persona_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0], "persona_id": row[1], "memory_content": row[2],
            "merge_version": row[3], "updated_at": row[4],
        }
    finally:
        await conn.close()


async def save_global_memory(persona_id: str, memory_content: str) -> dict:
    """保存合并后的全局记忆"""
    now = datetime.now(timezone.utc).isoformat()
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, merge_version FROM persona_global_memory WHERE persona_id = ?",
            (persona_id,),
        )
        existing = await cursor.fetchone()

        if existing:
            new_version = existing[1] + 1
            await conn.execute(
                """UPDATE persona_global_memory
                   SET memory_content = ?, merge_version = ?, updated_at = ?
                   WHERE persona_id = ?""",
                (memory_content, new_version, now, persona_id),
            )
            gm_id = existing[0]
        else:
            gm_id = str(uuid.uuid4())
            new_version = 1
            await conn.execute(
                """INSERT INTO persona_global_memory (id, persona_id, memory_content, merge_version, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (gm_id, persona_id, memory_content, new_version, now),
            )

        await conn.commit()
        return {"id": gm_id, "persona_id": persona_id, "merge_version": new_version, "updated_at": now}
    finally:
        await conn.close()


# ── 辅助函数 ──────────────────────────────────────────────────────

async def llm_merge_memories(
    persona_id: str,
    persona_content: str,
    current_global: str,
    node_memories: list[dict],
    max_chars: int,
) -> str | None:
    """用 LLM 智能合并多节点记忆

    将各节点记忆 + 当前全局记忆交给 LLM 去重、整合、提炼，
    同时进行人格一致性检查，剔除与人格定义矛盾的内容。

    Returns:
        合并后的记忆文本，LLM 不可用时返回 None（降级到简单合并）
    """
    from control_plane.llm_helper import llm_chat

    memory_sections = []
    for nm in node_memories:
        content = nm.get("memory_content", "").strip()
        if content:
            node_label = nm.get("node_id", "unknown")[:8]
            memory_sections.append(f"[节点 {node_label}]\n{content}")

    if not memory_sections:
        return current_global or ""

    prompt = f"""你是一个记忆整理专家。请将多个节点上报的记忆合并为一份统一的全局记忆。

## 人格定义（只读，不可修改）
{persona_content}

## 当前全局记忆
{current_global or "(空)"}

## 各节点上报的记忆
{"---".join(memory_sections)}

## 合并要求
1. 去重：相同或相似的经验只保留一份，合并细节
2. 提炼：将冗长的描述压缩为简洁的要点
3. 人格一致性检查：删除任何与上述人格定义矛盾的记忆条目（如人格定义要求"严谨"，但记忆中出现"随意猜测"的行为模式，应删除）
4. 保留价值：优先保留具体的技术经验、问题解决方案、决策模式
5. 字数限制：合并结果不超过 {max_chars} 字符
6. 时效性：如果多个节点对同一问题有不同经验，保留最新或最完整的版本

请直接输出合并后的记忆内容，不要加任何解释或前缀。"""

    result = await llm_chat(
        prompt=prompt,
        system="你是记忆整理专家，负责合并多源记忆并确保与人格定义一致。直接输出结果，不加解释。",
        max_tokens=max(2000, max_chars // 2),
    )
    return result


async def compress_memory(persona_id: str) -> dict | None:
    """定期压缩某个 Persona 的全局记忆

    读取当前全局记忆，用 LLM 提炼压缩，去除冗余和过时信息。
    适合定期调用（如每天一次）防止记忆膨胀。

    Returns:
        压缩结果 {"persona_id", "merge_version", "before_chars", "after_chars"} 或 None
    """
    from control_plane.llm_helper import llm_chat

    persona = await get_persona(persona_id)
    if not persona:
        return None

    gm = await get_global_memory(persona_id)
    if not gm or not gm["memory_content"].strip():
        return None

    current_content = gm["memory_content"]
    max_chars = persona["max_memory_chars"]

    # 如果记忆量不大（不到上限的 60%），不需要压缩
    if len(current_content) < max_chars * 0.6:
        return None

    prompt = f"""你是记忆压缩专家。请压缩以下长期记忆，去除冗余和过时信息。

## 人格定义（参考，确保压缩后记忆与人格一致）
{persona["persona_content"]}

## 当前记忆（需要压缩）
{current_content}

## 压缩要求
1. 保留核心经验和关键决策模式
2. 合并重复或相似的条目
3. 删除过于具体的细节（保留结论，删除过程）
4. 删除与人格定义矛盾的内容
5. 压缩后不超过 {int(max_chars * 0.5)} 字符
6. 保持结构化格式，便于后续检索

请直接输出压缩后的记忆内容。"""

    compressed = await llm_chat(
        prompt=prompt,
        system="你是记忆压缩专家，负责提炼和压缩长期记忆。直接输出结果。",
        max_tokens=max(2000, max_chars // 2),
    )

    if not compressed:
        return None

    # 保存压缩后的记忆
    result = await save_global_memory(persona_id, compressed)
    return {
        "persona_id": persona_id,
        "merge_version": result["merge_version"],
        "before_chars": len(current_content),
        "after_chars": len(compressed),
    }


def _row_to_persona(row) -> dict:
    return {
        "id": row[0], "name": row[1], "description": row[2],
        "persona_content": row[3], "version": row[4],
        "max_memory_chars": row[5], "created_at": row[6], "updated_at": row[7],
    }
