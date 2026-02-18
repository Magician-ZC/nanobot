"""ManagedHeartbeatService - 受管模式下的心跳服务

定期向 Control Plane 上报节点状态，检测策略/配置更新并触发回调。
连接中断时记录警告并继续运行，不中断心跳循环。
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from nanobot.managed.client import ControlPlaneError, HeartbeatResponse, ManagedClient

if TYPE_CHECKING:
    from nanobot.managed.audit import AuditLogger
    from nanobot.managed.log_collector import LogCollector
    from nanobot.managed.token_tracker import TokenTracker

logger = logging.getLogger(__name__)

# 状态收集器类型：返回当前节点状态的回调
StatusCollector = Callable[[], dict[str, Any]]

# 更新回调类型：收到更新通知时触发
UpdateCallback = Callable[[HeartbeatResponse], Awaitable[None]]


class ManagedHeartbeatService:
    """受管模式下的心跳服务，定期向 Control Plane 上报状态

    Args:
        client: ManagedClient 实例，用于与 Control Plane 通信
        on_update: 心跳响应指示有更新时的异步回调
        status_collector: 收集当前节点状态的回调，返回包含
            loaded_skills, connected_mcp_servers, active_tasks,
            config_version, policy_version 的字典
        interval: 心跳间隔（秒），默认 30
        log_collector: 可选的 LogCollector 实例，心跳时附带日志上报
        audit_logger: 可选的 AuditLogger 实例，心跳时附带审计日志同步
    """

    def __init__(
        self,
        client: ManagedClient,
        on_update: UpdateCallback,
        status_collector: StatusCollector | None = None,
        interval: int = 30,
        log_collector: "LogCollector | None" = None,
        audit_logger: "AuditLogger | None" = None,
        token_tracker: "TokenTracker | None" = None,
    ):
        self._client = client
        self._on_update = on_update
        self._status_collector = status_collector or self._default_status
        self._interval = interval
        self._log_collector = log_collector
        self._audit_logger = audit_logger
        self._token_tracker = token_tracker
        self._task: asyncio.Task[None] | None = None
        self._running = False

    @staticmethod
    def _default_status() -> dict[str, Any]:
        """默认状态收集器，返回空状态"""
        return {
            "loaded_skills": [],
            "connected_mcp_servers": [],
            "active_tasks": [],
            "config_version": 0,
            "policy_version": 0,
        }

    @property
    def running(self) -> bool:
        return self._running

    @property
    def interval(self) -> int:
        return self._interval

    async def start(self) -> None:
        """启动心跳循环（后台任务）"""
        if self._running:
            logger.warning("心跳服务已在运行中")
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("心跳服务已启动 (间隔=%d秒)", self._interval)

    async def stop(self) -> None:
        """停止心跳循环"""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("心跳服务已停止")

    async def _loop(self) -> None:
        """心跳主循环，按间隔执行 _tick"""
        while self._running:
            await self._tick()
            try:
                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                break

    async def _tick(self) -> None:
        """单次心跳：上报状态和日志，检查更新，触发回调

        连接失败时记录警告并继续运行，不抛出异常。
        日志上报失败时通过 mark_failed 回退，下次心跳重试。
        """
        try:
            status = self._status_collector()
            response = await self._client.heartbeat(
                loaded_skills=status.get("loaded_skills", []),
                connected_mcp_servers=status.get("connected_mcp_servers", []),
                active_tasks=status.get("active_tasks", []),
                config_version=status.get("config_version", 0),
                policy_version=status.get("policy_version", 0),
            )

            # 心跳成功后上报日志
            await self._upload_logs()

            # 心跳成功后上报 Token 用量
            await self._upload_token_usage()

            # 心跳成功后同步审计日志（违规记录优先）
            await self._sync_audit_logs()

            if response.has_policy_update or response.has_config_update:
                logger.info(
                    "收到更新通知: policy=%s, config=%s",
                    response.has_policy_update,
                    response.has_config_update,
                )
                try:
                    await self._on_update(response)
                except Exception:
                    logger.exception("更新回调执行失败")

        except ControlPlaneError as e:
            logger.warning("心跳发送失败 (Control Plane 错误): %s", e)
        except Exception:
            logger.warning("心跳发送失败 (连接中断)，将在下次间隔重试", exc_info=True)

    async def _upload_logs(self) -> None:
        """上报 LogCollector 中的日志，失败时回退"""
        if not self._log_collector:
            return

        entries = self._log_collector.drain()
        if not entries:
            return

        try:
            log_dicts = [e.to_dict() for e in entries]
            await self._client.upload_logs(log_dicts)
        except Exception:
            # 上报失败，回退日志到待发送队列
            self._log_collector.mark_failed(entries)
            logger.warning("日志上报失败，已回退 %d 条日志", len(entries))

    async def _sync_audit_logs(self) -> None:
        """同步 AuditLogger 中的未同步审计日志，失败时不回退（下次重试）"""
        if not self._audit_logger:
            return

        entries = self._audit_logger.get_unsynced()
        if not entries:
            return

        try:
            log_dicts = [e.to_dict() for e in entries]
            stored = await self._client.upload_audit_logs(log_dicts)
            if stored > 0:
                self._audit_logger.mark_synced([e.id for e in entries[:stored]])
                logger.info("审计日志同步成功: %d 条", stored)
        except Exception:
            logger.warning("审计日志同步失败，将在下次心跳重试 (%d 条待同步)", len(entries))

    async def _upload_token_usage(self) -> None:
        """上报 TokenTracker 中的用量记录，失败时回退"""
        if not self._token_tracker:
            return

        records = self._token_tracker.drain()
        if not records:
            return

        try:
            record_dicts = [r.to_dict() for r in records]
            await self._client.upload_token_usage(record_dicts)
        except Exception:
            self._token_tracker.mark_failed(records)
            logger.warning("Token 用量上报失败，已回退 %d 条记录", len(records))

