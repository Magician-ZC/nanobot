"""LogCollector - Agent Node 日志收集器

使用 deque 环形缓冲区收集运行日志，支持批量取出未上报日志（drain），
上报失败时回退（mark_failed），以及作为 logging.Handler 集成到现有日志系统。
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class LogEntry:
    """单条日志记录"""
    timestamp: str
    level: str
    message: str
    node_id: str = ""
    extra: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class LogCollector:
    """收集 Agent Node 运行日志，缓存并批量上报

    使用 deque 环形缓冲区（默认 1000 条），超出容量时自动丢弃最旧的日志。
    线程安全：所有操作通过锁保护。

    Args:
        buffer_size: 环形缓冲区最大容量
        node_id: 节点 ID，写入每条日志
    """

    def __init__(self, buffer_size: int = 1000, node_id: str = ""):
        self._buffer: deque[LogEntry] = deque(maxlen=buffer_size)
        self._unsent: list[LogEntry] = []
        self._lock = threading.Lock()
        self.node_id = node_id

    def emit(self, level: str, message: str, extra: dict | None = None) -> None:
        """记录一条日志到缓冲区"""
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=level.upper(),
            message=message,
            node_id=self.node_id,
            extra=extra,
        )
        with self._lock:
            self._buffer.append(entry)

    def drain(self) -> list[LogEntry]:
        """取出所有未上报的日志条目（心跳时调用）

        返回缓冲区中所有日志 + 之前上报失败回退的日志，
        按时间戳排序，取出后清空缓冲区和回退队列。
        """
        with self._lock:
            entries = list(self._unsent) + list(self._buffer)
            self._unsent.clear()
            self._buffer.clear()
        # 按时间戳排序，确保顺序
        entries.sort(key=lambda e: e.timestamp)
        return entries

    def mark_failed(self, entries: list[LogEntry]) -> None:
        """上报失败时将日志放回待发送队列

        放回的日志会在下次 drain() 时优先返回。
        """
        with self._lock:
            self._unsent.extend(entries)

    @property
    def pending_count(self) -> int:
        """待上报的日志总数（缓冲区 + 回退队列）"""
        with self._lock:
            return len(self._buffer) + len(self._unsent)


class LogCollectorHandler(logging.Handler):
    """将 Python logging 日志转发到 LogCollector 的 Handler

    作为额外的 handler 集成到现有日志系统，不影响其他 handler。

    Usage:
        collector = LogCollector(node_id="my-node")
        handler = LogCollectorHandler(collector)
        logging.getLogger().addHandler(handler)
    """

    def __init__(self, collector: LogCollector, level: int = logging.DEBUG):
        super().__init__(level)
        self.collector = collector

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record) if self.formatter else record.getMessage()
            extra = None
            if hasattr(record, "extra_data") and record.extra_data:
                extra = record.extra_data
            self.collector.emit(
                level=record.levelname,
                message=message,
                extra=extra,
            )
        except Exception:
            self.handleError(record)
