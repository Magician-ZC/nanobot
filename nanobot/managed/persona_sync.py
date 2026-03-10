"""PersonaSyncer — 从 Control Plane 同步 Persona 并上报记忆

同步流程：
1. 拉取策略中分配的 Persona 列表（人格定义 + 全局记忆）
2. 写入本地 personas/{name}/PERSONA.md（只读覆盖，不允许本地修改）
3. 将全局记忆写入 MEMORY.md（作为基础记忆，本地可追加）
4. 删除不在策略中的本地 Persona
5. 上报本地积累的记忆增量到 Control Plane
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nanobot.managed.client import ManagedClient

logger = logging.getLogger(__name__)


@dataclass
class PersonaSyncResult:
    """同步结果"""
    synced: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    uploaded: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


class PersonaSyncer:
    """从 Control Plane 同步 Persona 并上报记忆"""

    def __init__(self, client: "ManagedClient", personas_dir: Path):
        self._client = client
        self._personas_dir = personas_dir

    async def sync(self, allowed_personas: list[str]) -> PersonaSyncResult:
        """完整同步流程：拉取 → 写入 → 清理 → 上报"""
        result = PersonaSyncResult()
        allowed_set = set(allowed_personas)
        self._personas_dir.mkdir(parents=True, exist_ok=True)

        # 1. 拉取远程 Persona 数据
        try:
            remote_personas = await self._client.fetch_personas()
        except Exception:
            logger.exception("拉取 Persona 列表失败")
            return result

        remote_names = set()
        for rp in remote_personas:
            name = rp["name"]
            remote_names.add(name)
            try:
                self._write_persona_local(rp)
                result.synced.append(name)
            except Exception:
                logger.exception("写入 Persona '%s' 失败", name)
                result.failed.append(name)

        # 2. 删除不在策略中的本地 Persona
        if self._personas_dir.exists():
            for item in self._personas_dir.iterdir():
                if item.is_dir() and item.name not in allowed_set:
                    try:
                        import shutil
                        shutil.rmtree(item)
                        result.removed.append(item.name)
                        logger.info("已删除本地 Persona '%s'", item.name)
                    except OSError:
                        logger.exception("删除 Persona '%s' 失败", item.name)

        # 3. 上报本地记忆增量
        memories_to_upload = self._collect_local_memories(allowed_set)
        if memories_to_upload:
            try:
                await self._client.upload_persona_memory(memories_to_upload)
                result.uploaded = [m["persona_name"] for m in memories_to_upload]
                logger.info("上报 %d 个 Persona 记忆", len(memories_to_upload))
            except Exception:
                logger.exception("上报 Persona 记忆失败")

        logger.info(
            "Persona 同步完成: 同步=%d, 删除=%d, 上报=%d, 失败=%d",
            len(result.synced), len(result.removed),
            len(result.uploaded), len(result.failed),
        )
        return result

    def _write_persona_local(self, remote_data: dict) -> None:
        """将远程 Persona 数据写入本地文件"""
        name = remote_data["name"]
        persona_dir = self._personas_dir / name
        persona_dir.mkdir(parents=True, exist_ok=True)

        # 写入人格定义（只读覆盖）
        persona_file = persona_dir / "PERSONA.md"
        persona_file.write_text(remote_data["persona_content"], encoding="utf-8")

        # 写入全局记忆作为基础（仅当本地记忆为空或全局版本更新时）
        global_memory = remote_data.get("global_memory", "")
        if global_memory:
            memory_dir = persona_dir / "memory"
            memory_dir.mkdir(parents=True, exist_ok=True)
            memory_file = memory_dir / "MEMORY.md"

            # 版本标记文件，记录已同步的全局记忆版本
            version_file = persona_dir / ".global_memory_version"
            local_gm_version = 0
            if version_file.exists():
                try:
                    local_gm_version = int(version_file.read_text().strip())
                except (ValueError, OSError):
                    pass

            remote_gm_version = remote_data.get("global_memory_version", 0)
            if remote_gm_version > local_gm_version:
                # 合并策略：全局记忆作为基础，保留本地追加的内容
                local_memory = ""
                if memory_file.exists():
                    local_memory = memory_file.read_text(encoding="utf-8")

                if local_memory and local_memory != global_memory:
                    # 本地有额外内容，追加到全局记忆后面
                    merged = global_memory + "\n\n---\n\n## 本地经验补充\n\n" + local_memory
                else:
                    merged = global_memory

                memory_file.write_text(merged, encoding="utf-8")
                version_file.write_text(str(remote_gm_version))
                logger.info("Persona '%s' 全局记忆已更新到 v%d", name, remote_gm_version)

    def _collect_local_memories(self, allowed_names: set[str]) -> list[dict]:
        """收集本地 Persona 的记忆内容，准备上报"""
        memories = []
        for name in allowed_names:
            persona_dir = self._personas_dir / name
            memory_dir = persona_dir / "memory"
            memory_file = memory_dir / "MEMORY.md"
            history_file = memory_dir / "HISTORY.md"

            if not memory_file.exists():
                continue

            memory_content = memory_file.read_text(encoding="utf-8").strip()
            if not memory_content:
                continue

            history_entries = ""
            if history_file.exists():
                history_entries = history_file.read_text(encoding="utf-8").strip()

            memories.append({
                "persona_name": name,
                "memory_content": memory_content,
                "history_entries": history_entries,
            })

        return memories
