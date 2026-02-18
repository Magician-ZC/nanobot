"""ManagedMarker - 受管部署标记文件管理

管理 `.managed` 标记文件的创建、验证和检测。
标记文件用于标识通过一键部署安装的节点，强制以受管模式运行。
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# 默认路径
_NANOBOT_DIR = Path.home() / ".nanobot"
_MARKER_PATH = _NANOBOT_DIR / ".managed"
_CONFIG_CACHE_PATH = _NANOBOT_DIR / "config_cache.enc"
_CONFIG_PATH = _NANOBOT_DIR / "config.json"


class ManagedMarker:
    """受管部署标记文件管理

    标记文件 (~/.nanobot/.managed) 包含 Control Plane 地址的 SHA-256 指纹，
    用于标识该节点为受管部署，强制以受管模式运行。
    """

    def __init__(self, marker_path: Path = _MARKER_PATH):
        self._path = marker_path

    @property
    def path(self) -> Path:
        return self._path

    # ── 创建 ──────────────────────────────────────────────────────

    def create(self, control_plane_url: str) -> None:
        """创建受管标记文件，写入 Control Plane 地址的 SHA-256 指纹

        Args:
            control_plane_url: Control Plane 服务地址
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fingerprint = self._compute_fingerprint(control_plane_url)
        marker_data = {
            "control_plane_fingerprint": f"sha256:{fingerprint}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._path.write_text(json.dumps(marker_data, indent=2))
        logger.info("受管标记文件已创建: %s", self._path)

    # ── 检查 ──────────────────────────────────────────────────────

    def exists(self) -> bool:
        """检查受管标记文件是否存在"""
        return self._path.exists()

    # ── 验证 ──────────────────────────────────────────────────────

    def verify(self, control_plane_url: str) -> bool:
        """验证标记文件中的指纹与当前 Control Plane 地址是否匹配

        Args:
            control_plane_url: 要验证的 Control Plane 地址

        Returns:
            True 指纹匹配，False 不匹配或文件不存在/无效
        """
        if not self._path.exists():
            return False
        try:
            data = json.loads(self._path.read_text())
            stored = data.get("control_plane_fingerprint", "")
            expected = f"sha256:{self._compute_fingerprint(control_plane_url)}"
            return stored == expected
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("受管标记文件读取失败: %s", e)
            return False

    # ── 综合判断 ──────────────────────────────────────────────────

    def is_managed_deployment(
        self,
        config_cache_path: Path = _CONFIG_CACHE_PATH,
        config_path: Path = _CONFIG_PATH,
    ) -> bool:
        """综合判断是否为受管部署

        判断优先级：
        1. .managed 标记文件存在
        2. config_cache.enc 加密缓存存在
        3. config.json 中存在 controlPlane 配置段且 url 非空

        Args:
            config_cache_path: 加密配置缓存路径
            config_path: 配置文件路径

        Returns:
            True 为受管部署
        """
        # 1. 标记文件
        if self._path.exists():
            return True

        # 2. 加密缓存
        if config_cache_path.exists():
            return True

        # 3. config.json 中的 controlPlane 段
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text())
                cp = data.get("controlPlane", {})
                if cp.get("url"):
                    return True
            except (json.JSONDecodeError, OSError):
                pass

        return False

    # ── 工具方法 ──────────────────────────────────────────────────

    @staticmethod
    def _compute_fingerprint(url: str) -> str:
        """计算 URL 的 SHA-256 指纹"""
        return hashlib.sha256(url.encode()).hexdigest()
