"""TokenTracker - LLM Token 用量追踪

利用 LiteLLM 回调机制自动捕获每次 LLM 调用的 Token 用量，
缓存到本地队列，随心跳批量上报给 Control Plane。
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class TokenUsageRecord:
    """单次 LLM 调用的 Token 用量"""
    timestamp: str
    node_id: str
    model: str
    key_id: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "model": self.model,
            "key_id": self.key_id,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


class TokenTracker:
    """LLM Token 用量追踪器

    通过 on_llm_complete 回调记录用量，drain() 取出未上报记录，
    mark_failed() 在上报失败时回退。线程安全。

    Args:
        node_id: 节点 ID
        key_id: 当前分配的 LLM Key ID
    """

    def __init__(self, node_id: str, key_id: str = ""):
        self.node_id = node_id
        self.key_id = key_id
        self._records: list[TokenUsageRecord] = []
        self._lock = threading.Lock()

    def on_llm_complete(self, response: dict) -> None:
        """LiteLLM 回调：记录 Token 用量

        Args:
            response: LiteLLM 响应字典，包含 usage 和 model 字段
        """
        usage = response.get("usage", {})
        if not usage:
            return

        record = TokenUsageRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node_id=self.node_id,
            model=response.get("model", "unknown"),
            key_id=self.key_id,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )

        with self._lock:
            self._records.append(record)

        logger.debug(
            "Token 用量记录: model=%s, total=%d",
            record.model, record.total_tokens,
        )

    def drain(self) -> list[TokenUsageRecord]:
        """取出所有未上报的用量记录（心跳时调用）"""
        with self._lock:
            records = self._records[:]
            self._records.clear()
        return records

    def mark_failed(self, records: list[TokenUsageRecord]) -> None:
        """上报失败时放回待发送队列"""
        with self._lock:
            self._records = records + self._records

    @property
    def pending_count(self) -> int:
        """待上报记录数"""
        with self._lock:
            return len(self._records)
