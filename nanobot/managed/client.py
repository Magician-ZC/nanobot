"""ManagedClient - 与 Control Plane 通信的 HTTP 客户端

使用 httpx.AsyncClient 实现与 Control Plane 的 REST API 通信，
包含连接错误处理和重试逻辑。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# 默认重试配置
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0  # 秒
DEFAULT_TIMEOUT = 30.0  # 秒


@dataclass
class ResourcePolicy:
    """资源策略"""
    allowed_skills: list[str] = field(default_factory=list)
    allowed_mcp_servers: list[str] = field(default_factory=list)
    version: int = 0
    skill_versions: dict[str, dict] = field(default_factory=dict)
    # skill_versions 格式: {"skill_name": {"version": 1, "checksum": "sha256:..."}, ...}


@dataclass
class HeartbeatResponse:
    """心跳响应"""
    has_policy_update: bool = False
    has_config_update: bool = False
    latest_policy_version: int = 0
    latest_config_version: int = 0
    has_skill_update: bool = False


@dataclass
class TaskLock:
    """任务锁"""
    lock_id: str = ""
    resource: str = ""
    node_id: str = ""
    description: str = ""
    acquired_at: str = ""
    expires_at: str = ""


class ControlPlaneError(Exception):
    """Control Plane 通信错误基类"""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(ControlPlaneError):
    """认证失败（401）"""
    pass


class PermissionError(ControlPlaneError):
    """权限不足（403）"""
    pass


class NotFoundError(ControlPlaneError):
    """资源不存在（404）"""
    pass


class ConflictError(ControlPlaneError):
    """资源冲突（409）"""
    pass


class ManagedClient:
    """与 Control Plane 通信的 HTTP 客户端

    使用 httpx.AsyncClient 实现异步 HTTP 通信，
    支持连接错误自动重试和统一的错误处理。
    """

    def __init__(
        self,
        control_plane_url: str,
        api_key: str = "",
        node_id: str = "",
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.base_url = control_plane_url.rstrip("/")
        self.api_key = api_key
        self.node_id = node_id
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
        )

    def _headers(self) -> dict[str, str]:
        """构建请求头，包含 API Key 认证"""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any] | None:
        """统一的 HTTP 请求方法，包含重试和错误处理

        Args:
            method: HTTP 方法 (GET, POST, PUT, DELETE)
            path: API 路径 (如 /api/nodes/register)
            json: 请求体 JSON 数据
            params: 查询参数

        Returns:
            响应 JSON 数据，204 响应返回 None

        Raises:
            ControlPlaneError: 通信或业务错误
        """
        import asyncio

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = await self._client.request(
                    method,
                    path,
                    json=json,
                    params=params,
                    headers=self._headers(),
                )
                return self._handle_response(response)

            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
                last_error = e
                if attempt < self.max_retries:
                    wait = self.retry_delay * (2 ** (attempt - 1))  # 指数退避
                    logger.warning(
                        "Control Plane 连接失败 (尝试 %d/%d)，%0.1f 秒后重试: %s",
                        attempt, self.max_retries, wait, e,
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(
                        "Control Plane 连接失败，已达最大重试次数 (%d): %s",
                        self.max_retries, e,
                    )

        raise ControlPlaneError(
            f"无法连接 Control Plane ({self.base_url}): {last_error}"
        )

    @staticmethod
    def _handle_response(response: httpx.Response) -> dict[str, Any] | list[Any] | None:
        """处理 HTTP 响应，将错误状态码转换为异常"""
        if response.status_code == 204:
            return None

        if response.status_code in (200, 201):
            return response.json()

        # 提取错误详情
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text

        status = response.status_code
        msg = f"Control Plane 返回错误 ({status}): {detail}"

        if status == 401:
            raise AuthenticationError(msg, status)
        elif status == 403:
            raise PermissionError(msg, status)
        elif status == 404:
            raise NotFoundError(msg, status)
        elif status == 409:
            raise ConflictError(msg, status)
        else:
            raise ControlPlaneError(msg, status)

    # ── 节点注册 ──────────────────────────────────────────────────

    async def register(self, token: str, hostname: str) -> dict[str, str]:
        """使用注册令牌注册节点

        Args:
            token: 一次性注册令牌
            hostname: 节点主机名

        Returns:
            {"node_id": "...", "api_key": "..."}

        Raises:
            ControlPlaneError: 令牌无效、过期或已使用
        """
        result = await self._request(
            "POST",
            "/api/nodes/register",
            json={"token": token, "hostname": hostname},
        )
        data = result  # type: ignore[assignment]
        # 注册成功后更新本地状态
        self.node_id = data["node_id"]
        self.api_key = data["api_key"]
        logger.info("节点注册成功: node_id=%s", self.node_id)
        return data

    # ── 心跳 ──────────────────────────────────────────────────────

    async def heartbeat(
        self,
        loaded_skills: list[str] | None = None,
        connected_mcp_servers: list[str] | None = None,
        active_tasks: list[str] | None = None,
        config_version: int = 0,
        policy_version: int = 0,
    ) -> HeartbeatResponse:
        """发送心跳，上报节点状态

        Args:
            loaded_skills: 当前加载的 Skill 列表
            connected_mcp_servers: 已连接的 MCP Server 列表
            active_tasks: 活跃任务列表
            config_version: 当前配置版本号
            policy_version: 当前策略版本号

        Returns:
            HeartbeatResponse 包含是否有策略/配置更新
        """
        payload = {
            "node_id": self.node_id,
            "loaded_skills": loaded_skills or [],
            "connected_mcp_servers": connected_mcp_servers or [],
            "active_tasks": active_tasks or [],
            "config_version": config_version,
            "policy_version": policy_version,
        }
        result = await self._request(
            "POST",
            f"/api/nodes/{self.node_id}/heartbeat",
            json=payload,
        )
        data = result  # type: ignore[assignment]
        return HeartbeatResponse(
            has_policy_update=data.get("has_policy_update", False),
            has_config_update=data.get("has_config_update", False),
            latest_policy_version=data.get("latest_policy_version", 0),
            latest_config_version=data.get("latest_config_version", 0),
        )

    # ── 策略拉取 ──────────────────────────────────────────────────

    async def fetch_policy(self) -> ResourcePolicy:
        """拉取最新的资源策略

        Returns:
            ResourcePolicy 包含允许的 Skill 和 MCP Server 列表及 Skill 版本信息
        """
        result = await self._request("GET", f"/api/nodes/{self.node_id}/policy")
        data = result  # type: ignore[assignment]
        return ResourcePolicy(
            allowed_skills=data.get("allowed_skills", []),
            allowed_mcp_servers=data.get("allowed_mcp_servers", []),
            version=data.get("version", 0),
            skill_versions=data.get("skill_versions", {}),
        )

    # ── 配置拉取 ──────────────────────────────────────────────────

    async def fetch_config(self) -> dict[str, Any]:
        """拉取最新的远程配置

        Returns:
            包含 config_data 和 version 的字典
        """
        result = await self._request("GET", f"/api/nodes/{self.node_id}/config")
        data = result  # type: ignore[assignment]
        return {
            "config_data": data.get("config_data", {}),
            "version": data.get("version", 0),
        }

    # ── 任务锁 ────────────────────────────────────────────────────

    async def acquire_task_lock(
        self,
        resource: str,
        description: str = "",
        timeout_minutes: int = 10,
    ) -> TaskLock | None:
        """获取任务锁

        Args:
            resource: 锁定的资源标识
            description: 任务描述
            timeout_minutes: 锁超时时间（分钟）

        Returns:
            TaskLock 对象，资源已被锁定时返回 None
        """
        try:
            result = await self._request(
                "POST",
                "/api/tasks/lock",
                json={
                    "node_id": self.node_id,
                    "resource": resource,
                    "description": description,
                    "timeout_minutes": timeout_minutes,
                },
            )
        except ConflictError:
            logger.warning("资源 '%s' 已被锁定", resource)
            return None

        data = result  # type: ignore[assignment]
        return TaskLock(
            lock_id=data["id"],
            resource=data["resource"],
            node_id=data["node_id"],
            description=data.get("description", ""),
            acquired_at=data.get("acquired_at", ""),
            expires_at=data.get("expires_at", ""),
        )

    async def release_task_lock(self, lock_id: str) -> bool:
        """释放任务锁

        Args:
            lock_id: 锁 ID

        Returns:
            True 释放成功，False 锁不存在
        """
        try:
            await self._request("DELETE", f"/api/tasks/lock/{lock_id}")
            return True
        except NotFoundError:
            logger.warning("任务锁 '%s' 不存在", lock_id)
            return False

    # ── 日志上报 ──────────────────────────────────────────────────────

    async def upload_logs(self, logs: list[dict]) -> int:
        """批量上报日志到 Control Plane

        Args:
            logs: 日志条目列表，每条包含 timestamp, level, message, extra

        Returns:
            成功存储的日志条数
        """
        if not logs:
            return 0
        result = await self._request(
            "POST",
            f"/api/nodes/{self.node_id}/logs",
            json={"logs": logs},
        )
        data = result  # type: ignore[assignment]
        return data.get("stored", 0)

    async def upload_audit_logs(self, logs: list[dict]) -> int:
        """批量上报审计日志到 Control Plane

        Args:
            logs: 审计日志条目列表

        Returns:
            成功存储的条数
        """
        if not logs:
            return 0
        result = await self._request(
            "POST",
            f"/api/nodes/{self.node_id}/audit",
            json={"logs": logs},
        )
        data = result  # type: ignore[assignment]
        return data.get("stored", 0)
    async def upload_audit_logs(self, logs: list[dict]) -> int:
        """批量上报审计日志到 Control Plane

        Args:
            logs: 审计日志条目列表

        Returns:
            成功存储的条数
        """
        if not logs:
            return 0
        result = await self._request(
            "POST",
            f"/api/nodes/{self.node_id}/audit",
            json={"logs": logs},
        )
        data = result  # type: ignore[assignment]
        return data.get("stored", 0)

    async def upload_token_usage(self, records: list[dict]) -> int:
        """批量上报 Token 用量到 Control Plane

        Args:
            records: Token 用量记录列表

        Returns:
            成功存储的记录数
        """
        if not records:
            return 0
        result = await self._request(
            "POST",
            f"/api/nodes/{self.node_id}/token-usage",
            json={"records": records},
        )
        data = result  # type: ignore[assignment]
        return data.get("stored", 0)

    async def report_ratelimit(self, key_id: str) -> dict | None:
        """上报限流事件

        Args:
            key_id: 被限流的 Key ID

        Returns:
            新分配的 Key 信息或 None
        """
        try:
            result = await self._request(
                "POST",
                f"/api/nodes/{self.node_id}/report-ratelimit",
                json={"key_id": key_id},
            )
            return result  # type: ignore[return-value]
        except ControlPlaneError:
            logger.warning("限流上报失败")
            return None

    async def download_skill(
        self, name: str, version: int | None = None
    ) -> tuple[bytes, str] | None:
        """下载 Skill 包

        Args:
            name: Skill 名称
            version: 指定版本号，None 则下载最新版本

        Returns:
            (文件内容, SHA-256 校验和) 或 None（不存在时）
        """
        import asyncio

        params: dict[str, Any] = {}
        if version is not None:
            params["version"] = version

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await self._client.get(
                    f"/api/skills/{name}/download",
                    params=params,
                    headers=self._headers(),
                )
                if response.status_code == 404:
                    return None
                if response.status_code >= 400:
                    self._handle_response(response)
                checksum = response.headers.get("x-checksum-sha256", "")
                return response.content, checksum
            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
                last_error = e
                if attempt < self.max_retries:
                    wait = self.retry_delay * (2 ** (attempt - 1))
                    await asyncio.sleep(wait)

        raise ControlPlaneError(
            f"无法下载 Skill '{name}': {last_error}"
        )



    # ── 生命周期 ──────────────────────────────────────────────────

    async def close(self) -> None:
        """关闭 HTTP 客户端"""
        await self._client.aclose()

    async def __aenter__(self) -> "ManagedClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
