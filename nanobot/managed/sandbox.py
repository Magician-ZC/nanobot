"""FileSandbox - 文件操作沙箱，限制路径在 Workspace 范围内

Requirements: 7.1, 7.2, 7.3, 7.4
"""

from pathlib import Path


class FileSandbox:
    """文件操作沙箱，限制路径在 Workspace 范围内。

    所有文件操作必须通过此类验证路径合法性，
    确保目标路径不会逃逸出配置的 Workspace 目录。
    """

    def __init__(self, workspace: Path):
        """初始化沙箱。

        Args:
            workspace: Workspace 根目录路径，必须是已存在的目录。

        Raises:
            ValueError: workspace 路径不存在或不是目录。
        """
        resolved = Path(workspace).resolve()
        if not resolved.is_dir():
            raise ValueError(f"Workspace 路径不存在或不是目录: {resolved}")
        self._workspace = resolved

    @property
    def workspace(self) -> Path:
        """返回 Workspace 根目录的规范化绝对路径。"""
        return self._workspace

    def resolve_safe(self, target: str) -> Path:
        """规范化路径，解析符号链接和相对路径组件。

        将目标路径解析为绝对路径：
        - 相对路径基于 Workspace 目录解析
        - 绝对路径直接解析
        - 解析所有 `..`、`.` 和符号链接

        不检查路径是否在 Workspace 内，仅做规范化。

        Args:
            target: 目标路径字符串。

        Returns:
            规范化后的绝对路径。
        """
        target_path = Path(target)
        if target_path.is_absolute():
            return target_path.resolve()
        return (self._workspace / target_path).resolve()

    def validate_path(self, target: str) -> Path:
        """验证路径在 Workspace 范围内。

        先通过 resolve_safe 规范化路径，再检查是否在 Workspace 内。
        Workspace 自身也是合法路径。

        Args:
            target: 目标路径字符串。

        Returns:
            验证通过的规范化绝对路径。

        Raises:
            PermissionError: 路径解析后超出 Workspace 范围。
        """
        resolved = self.resolve_safe(target)

        # 检查解析后的路径是否在 workspace 内
        # 使用 is_relative_to 判断（workspace 自身也合法）
        if not self._is_within_workspace(resolved):
            raise PermissionError(
                f"路径越界: '{target}' 解析为 '{resolved}'，"
                f"超出 Workspace 范围 '{self._workspace}'"
            )
        return resolved

    def _is_within_workspace(self, resolved: Path) -> bool:
        """检查已解析的路径是否在 Workspace 范围内。

        Args:
            resolved: 已规范化的绝对路径。

        Returns:
            True 如果路径在 Workspace 内或等于 Workspace。
        """
        try:
            resolved.relative_to(self._workspace)
            return True
        except ValueError:
            return False
