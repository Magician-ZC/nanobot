"""PolicyEnforcer - 在 Agent Node 端执行资源策略

根据 Control Plane 下发的 ResourcePolicy 过滤本地 Skill 和 MCP Server，
并提供策略的本地缓存能力，支持离线运行。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nanobot.managed.client import ResourcePolicy

logger = logging.getLogger(__name__)

# 默认缓存路径
DEFAULT_CACHE_PATH = Path("~/.nanobot/policy_cache.json").expanduser()


class PolicyEnforcer:
    """在 Agent Node 端执行资源策略，过滤 Skill 和 MCP Server"""

    # 默认最大离线时长（小时）
    DEFAULT_MAX_OFFLINE_HOURS = 24

    def __init__(self, policy: ResourcePolicy, cache_path: Path = DEFAULT_CACHE_PATH):
        self._policy = policy
        self._cache_path = cache_path
        self._cached_at: str | None = None
        self._strict_mode = False
        self._audit_logger: Any | None = None

    @property
    def audit_logger(self) -> Any | None:
        """关联的审计日志记录器"""
        return self._audit_logger

    @audit_logger.setter
    def audit_logger(self, value: Any) -> None:
        self._audit_logger = value

    @property
    def policy(self) -> ResourcePolicy:
        return self._policy

    @policy.setter
    def policy(self, value: ResourcePolicy) -> None:
        self._policy = value

    @property
    def cached_at(self) -> str | None:
        return self._cached_at

    @property
    def strict_mode(self) -> bool:
        """是否处于只读严格模式"""
        return self._strict_mode

    @property
    def cache_age_hours(self) -> float:
        """返回缓存策略的年龄（小时），无缓存时间戳则返回 inf"""
        if not self._cached_at:
            return float("inf")
        try:
            cached_time = datetime.fromisoformat(self._cached_at)
            # 确保时区感知
            if cached_time.tzinfo is None:
                cached_time = cached_time.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = now - cached_time
            return delta.total_seconds() / 3600.0
        except (ValueError, TypeError):
            return float("inf")

    def is_offline_allowed(self, max_offline_hours: int | None = None) -> bool:
        """检查离线时长是否在允许范围内

        Args:
            max_offline_hours: 最大允许离线时长（小时），None 则使用默认值 24

        Returns:
            True 表示离线时长在允许范围内，False 表示已超时
        """
        if max_offline_hours is None:
            max_offline_hours = self.DEFAULT_MAX_OFFLINE_HOURS
        return self.cache_age_hours <= max_offline_hours

    def enforce_strict_mode(self) -> None:
        """进入只读严格模式，离线超时后调用

        只读模式下仅允许查询操作，不允许执行新任务。
        """
        self._strict_mode = True
        logger.warning("策略执行器进入只读严格模式（离线超时）")

    @staticmethod
    def check_offline_startup(cache_path: Path = DEFAULT_CACHE_PATH) -> bool:
        """检查离线状态下是否可以启动受管模式

        Args:
            cache_path: 策略缓存文件路径

        Returns:
            True 表示有缓存可用，False 表示无缓存应拒绝启动
        """
        if not cache_path.exists():
            logger.error("离线状态下无缓存策略，拒绝以受管模式启动")
            return False
        return True

    def filter_skills(self, all_skills: list[dict]) -> list[dict]:
        """根据策略过滤可用的 Skill 列表

        返回 all_skills 与 allowed_skills 的交集。
        未授权的 Skill 会记录警告日志，并通过审计日志记录违规。

        Args:
            all_skills: 所有可用 Skill 列表，每个元素需包含 "name" 字段

        Returns:
            仅包含策略允许的 Skill 列表
        """
        allowed = set(self._policy.allowed_skills)
        result = []
        for skill in all_skills:
            name = skill.get("name", "")
            if name in allowed:
                result.append(skill)
            else:
                logger.warning("Skill '%s' 未在策略允许列表中，已跳过", name)
                if self._audit_logger:
                    self._audit_logger.log_violation(
                        "skill_call", {"skill": name, "reason": "not_in_policy"}
                    )
        return result

    def filter_mcp_servers(self, all_servers: dict) -> dict:
        """根据策略过滤可用的 MCP Server 配置

        返回 all_servers 与 allowed_mcp_servers 的交集。
        未授权的 MCP Server 会记录警告日志，并通过审计日志记录违规。

        Args:
            all_servers: 所有 MCP Server 配置字典，key 为服务器名称

        Returns:
            仅包含策略允许的 MCP Server 配置字典
        """
        allowed = set(self._policy.allowed_mcp_servers)
        result = {}
        for name, config in all_servers.items():
            if name in allowed:
                result[name] = config
            else:
                logger.warning("MCP Server '%s' 未在策略允许列表中，已跳过", name)
                if self._audit_logger:
                    self._audit_logger.log_violation(
                        "mcp_call", {"server": name, "reason": "not_in_policy"}
                    )
        return result

    def filter_personas(self, all_persona_names: list[str]) -> list[str]:
        """根据策略过滤可用的 Persona 列表

        Args:
            all_persona_names: 所有本地 Persona 名称

        Returns:
            仅包含策略允许的 Persona 名称列表
        """
        allowed = set(self._policy.allowed_personas)
        result = []
        for name in all_persona_names:
            if name in allowed:
                result.append(name)
            else:
                logger.warning("Persona '%s' 未在策略允许列表中，已跳过", name)
                if self._audit_logger:
                    self._audit_logger.log_violation(
                        "persona_access", {"persona": name, "reason": "not_in_policy"}
                    )
        return result

    def save_cache(self) -> None:
        """将策略缓存到本地文件系统

        缓存为 JSON 格式，包含策略内容、Skill 版本信息和缓存时间戳。
        """
        self._cached_at = datetime.now(timezone.utc).isoformat()
        cache_data = {
            "allowed_skills": self._policy.allowed_skills,
            "allowed_mcp_servers": self._policy.allowed_mcp_servers,
            "allowed_personas": self._policy.allowed_personas,
            "policy_version": self._policy.version,
            "skill_versions": self._policy.skill_versions,
            "persona_versions": self._policy.persona_versions,
            "cached_at": self._cached_at,
        }
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(json.dumps(cache_data, ensure_ascii=False, indent=2))
        logger.info("策略缓存已保存到 %s (version=%d)", self._cache_path, self._policy.version)

    @classmethod
    def load_from_cache(cls, cache_path: Path = DEFAULT_CACHE_PATH) -> PolicyEnforcer | None:
        """从本地缓存加载策略

        Args:
            cache_path: 缓存文件路径

        Returns:
            PolicyEnforcer 实例，缓存不存在或无效时返回 None
        """
        if not cache_path.exists():
            logger.info("策略缓存文件不存在: %s", cache_path)
            return None

        try:
            data = json.loads(cache_path.read_text())
            policy = ResourcePolicy(
                allowed_skills=data.get("allowed_skills", []),
                allowed_mcp_servers=data.get("allowed_mcp_servers", []),
                allowed_personas=data.get("allowed_personas", []),
                version=data.get("policy_version", 0),
                skill_versions=data.get("skill_versions", {}),
                persona_versions=data.get("persona_versions", {}),
            )
            enforcer = cls(policy=policy, cache_path=cache_path)
            enforcer._cached_at = data.get("cached_at")
            logger.info("从缓存加载策略成功 (version=%d)", policy.version)
            return enforcer
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error("策略缓存文件解析失败: %s", e)
            return None
