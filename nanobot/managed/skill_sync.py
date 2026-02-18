"""SkillSyncer - 从 Control Plane 下载和同步 Skill 文件

根据策略同步 Skill：下载新增、删除移除、更新变更版本。
下载后验证 SHA-256 校验和，校验失败则拒绝安装。
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nanobot.managed.client import ManagedClient

logger = logging.getLogger(__name__)


@dataclass
class SkillVersionInfo:
    """Skill 版本信息"""
    version: int = 0
    checksum: str = ""


@dataclass
class SyncResult:
    """同步结果"""
    downloaded: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


class SkillSyncer:
    """从 Control Plane 下载和同步 Skill 文件"""

    def __init__(self, client: ManagedClient, local_skill_dir: Path):
        self._client = client
        self._skill_dir = local_skill_dir

    async def sync(
        self,
        allowed_skills: list[str],
        skill_versions: dict[str, SkillVersionInfo] | None = None,
        local_versions: dict[str, SkillVersionInfo] | None = None,
    ) -> SyncResult:
        """根据策略同步 Skill 文件

        Args:
            allowed_skills: 策略允许的 Skill 名称列表
            skill_versions: 远程 Skill 版本信息（来自策略）
            local_versions: 本地已有的 Skill 版本信息

        Returns:
            SyncResult 包含下载、删除、更新和失败的 Skill 列表
        """
        result = SyncResult()
        skill_versions = skill_versions or {}
        local_versions = local_versions or {}
        allowed_set = set(allowed_skills)

        # 确保本地目录存在
        self._skill_dir.mkdir(parents=True, exist_ok=True)

        # 1. 下载新增和更新变更的 Skill
        for name in allowed_skills:
            remote_info = skill_versions.get(name)
            local_info = local_versions.get(name)
            local_path = self._skill_dir / name

            if local_info and remote_info:
                # 版本相同则跳过
                if local_info.version >= remote_info.version:
                    continue
                # 版本不同则更新
                ok = await self.download_skill(
                    name, remote_info.version, remote_info.checksum
                )
                if ok:
                    result.updated.append(name)
                else:
                    result.failed.append(name)
            elif not local_path.exists():
                # 本地不存在，下载
                version = remote_info.version if remote_info else None
                checksum = remote_info.checksum if remote_info else None
                ok = await self.download_skill(name, version, checksum)
                if ok:
                    result.downloaded.append(name)
                else:
                    result.failed.append(name)

        # 2. 删除不在策略中的本地 Skill
        if self._skill_dir.exists():
            for item in self._skill_dir.iterdir():
                if item.is_dir() and item.name not in allowed_set:
                    if self.remove_skill(item.name):
                        result.removed.append(item.name)

        logger.info(
            "Skill 同步完成: 下载=%d, 更新=%d, 删除=%d, 失败=%d",
            len(result.downloaded), len(result.updated),
            len(result.removed), len(result.failed),
        )
        return result

    async def download_skill(
        self,
        name: str,
        version: int | None = None,
        expected_checksum: str | None = None,
    ) -> bool:
        """下载 Skill 包并验证 SHA-256 校验和

        Args:
            name: Skill 名称
            version: 指定版本号
            expected_checksum: 期望的 SHA-256 校验和

        Returns:
            是否下载成功
        """
        try:
            result = await self._client.download_skill(name, version)
            if result is None:
                logger.error("Skill '%s' 在 Control Plane 中不存在", name)
                return False

            file_data, remote_checksum = result

            # 验证校验和
            actual_checksum = hashlib.sha256(file_data).hexdigest()
            if expected_checksum and actual_checksum != expected_checksum:
                logger.error(
                    "Skill '%s' 校验和不匹配: 期望=%s, 实际=%s",
                    name, expected_checksum, actual_checksum,
                )
                return False
            if remote_checksum and actual_checksum != remote_checksum:
                logger.error(
                    "Skill '%s' 校验和不匹配 (remote header): 期望=%s, 实际=%s",
                    name, remote_checksum, actual_checksum,
                )
                return False

            # 解压到本地目录
            target_dir = self._skill_dir / name
            if target_dir.exists():
                shutil.rmtree(target_dir)
            target_dir.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(BytesIO(file_data)) as zf:
                zf.extractall(target_dir)

            logger.info("Skill '%s' (v%s) 下载并安装成功", name, version or "latest")
            return True

        except Exception:
            logger.exception("下载 Skill '%s' 失败", name)
            return False

    def remove_skill(self, name: str) -> bool:
        """删除本地 Skill 文件

        Args:
            name: Skill 名称

        Returns:
            是否成功删除
        """
        target_dir = self._skill_dir / name
        if not target_dir.exists():
            return False
        try:
            shutil.rmtree(target_dir)
            logger.info("已删除本地 Skill '%s'", name)
            return True
        except OSError:
            logger.exception("删除 Skill '%s' 失败", name)
            return False
