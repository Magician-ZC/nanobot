"""MEDIA tag parser for extracting media file paths from agent responses.

Supports format:
    MEDIA:/path/to/file.png
    MEDIA:./relative/path.pdf
    MEDIA:https://example.com/image.jpg
"""

import re
from pathlib import Path

# 匹配 MEDIA: 标记（支持绝对路径、相对路径、URL）
MEDIA_PATTERN = re.compile(r"^MEDIA:(.+)$", re.MULTILINE)
# 兼容旧格式 [image:/path/to/file] (inline)
LEGACY_IMAGE_PATTERN = re.compile(r"\[image:(.+?)\]")


def parse_media_tags(content: str) -> tuple[str, list[str]]:
    """Parse MEDIA: and legacy [image:] tags from content.

    Args:
        content: Raw agent response text.

    Returns:
        Tuple of (cleaned_content, media_paths).
    """
    media_paths: list[str] = []

    def _collect_media(match: re.Match) -> str:
        path = match.group(1).strip()
        if path:
            media_paths.append(path)
        return ""

    def _collect_legacy(match: re.Match) -> str:
        path = match.group(1).strip()
        if path:
            media_paths.append(path)
        return ""

    # 先解析新格式 MEDIA:
    cleaned = MEDIA_PATTERN.sub(_collect_media, content)
    # 再解析旧格式 [image:]
    cleaned = LEGACY_IMAGE_PATTERN.sub(_collect_legacy, cleaned)
    cleaned = cleaned.strip()
    # 清理多余空行
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned, media_paths


def validate_media_path(path: str, workspace: Path | None = None) -> bool:
    """Validate that a media path is safe to access.

    Rules:
        - Allow https:// URLs
        - Allow relative paths
        - Allow absolute paths to existing files (agent-generated paths are trusted)
        - Reject paths with directory traversal attempts
    """
    # URL 直接放行
    if path.startswith(("https://", "http://")):
        return True

    # 拒绝明显的路径穿越
    if ".." in path:
        return False

    p = Path(path)

    # 相对路径：允许
    if not p.is_absolute():
        return True

    # 绝对路径：文件存在即允许（agent 生成的路径可信）
    if p.is_file():
        return True

    # 绝对路径但文件不存在：检查是否在 workspace 内
    if workspace:
        try:
            p.resolve().relative_to(workspace.resolve())
            return True
        except ValueError:
            return False

    return False
