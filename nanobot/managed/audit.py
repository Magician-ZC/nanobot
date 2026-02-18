"""AuditLogger - 本地审计日志记录器

记录所有操作到本地审计日志文件（JSONL 格式），支持离线积累和恢复后同步。
违规操作会被标记为优先上报。
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# 默认审计日志路径
DEFAULT_AUDIT_PATH = Path("~/.nanobot/audit_log.jsonl").expanduser()

# 有效的操作类型
VALID_OPERATION_TYPES = {"skill_call", "mcp_call", "file_op", "task_exec"}

# 有效的结果类型
VALID_RESULTS = {"success", "failed", "denied"}


@dataclass
class AuditEntry:
    """审计日志条目"""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    node_id: str = ""
    operation_type: str = ""
    details: dict = field(default_factory=dict)
    result: str = "success"
    is_violation: bool = False
    is_synced: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> AuditEntry:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class AuditLogger:
    """本地审计日志记录器，支持离线积累和恢复后同步

    日志以 JSONL 格式写入本地文件，每行一条 JSON 记录。
    支持获取未同步条目并在同步成功后标记。

    Args:
        audit_path: 审计日志文件路径
        node_id: 当前节点 ID
    """

    def __init__(self, audit_path: Path = DEFAULT_AUDIT_PATH, node_id: str = ""):
        self._audit_path = audit_path
        self._node_id = node_id
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def audit_path(self) -> Path:
        return self._audit_path

    @property
    def node_id(self) -> str:
        return self._node_id

    def log(self, operation_type: str, details: dict, result: str = "success") -> AuditEntry:
        """记录一条审计日志

        Args:
            operation_type: 操作类型 (skill_call, mcp_call, file_op, task_exec)
            details: 操作详情
            result: 执行结果 (success, failed, denied)

        Returns:
            创建的审计日志条目
        """
        entry = AuditEntry(
            node_id=self._node_id,
            operation_type=operation_type,
            details=details,
            result=result,
            is_violation=False,
        )
        self._append_entry(entry)
        return entry

    def log_violation(self, operation_type: str, details: dict) -> AuditEntry:
        """记录安全违规事件（优先上报）

        Args:
            operation_type: 操作类型
            details: 违规详情

        Returns:
            创建的审计日志条目
        """
        entry = AuditEntry(
            node_id=self._node_id,
            operation_type=operation_type,
            details=details,
            result="denied",
            is_violation=True,
        )
        self._append_entry(entry)
        logger.warning("安全违规: %s - %s", operation_type, details)
        return entry

    def get_unsynced(self) -> list[AuditEntry]:
        """获取所有未同步的审计日志条目

        违规记录排在前面（优先上报）。

        Returns:
            未同步的审计日志条目列表
        """
        entries = self._read_all()
        unsynced = [e for e in entries if not e.is_synced]
        # 违规记录优先
        unsynced.sort(key=lambda e: (not e.is_violation, e.timestamp))
        return unsynced

    def mark_synced(self, entry_ids: list[str]) -> int:
        """标记日志条目为已同步

        Args:
            entry_ids: 要标记的条目 ID 列表

        Returns:
            实际标记的条目数
        """
        if not entry_ids:
            return 0

        ids_set = set(entry_ids)
        entries = self._read_all()
        count = 0
        for entry in entries:
            if entry.id in ids_set and not entry.is_synced:
                entry.is_synced = True
                count += 1

        # 重写整个文件
        self._write_all(entries)
        return count

    def _append_entry(self, entry: AuditEntry) -> None:
        """追加一条审计日志到文件"""
        try:
            with open(self._audit_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        except OSError as e:
            logger.error("写入审计日志失败: %s", e)

    def _read_all(self) -> list[AuditEntry]:
        """读取所有审计日志条目"""
        if not self._audit_path.exists():
            return []
        entries = []
        try:
            with open(self._audit_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        entries.append(AuditEntry.from_dict(data))
                    except (json.JSONDecodeError, TypeError):
                        logger.warning("跳过无效的审计日志行")
        except OSError as e:
            logger.error("读取审计日志失败: %s", e)
        return entries

    def _write_all(self, entries: list[AuditEntry]) -> None:
        """重写所有审计日志条目到文件"""
        try:
            with open(self._audit_path, "w", encoding="utf-8") as f:
                for entry in entries:
                    f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        except OSError as e:
            logger.error("重写审计日志失败: %s", e)
