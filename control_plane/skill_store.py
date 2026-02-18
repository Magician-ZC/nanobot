"""Skill Store - Skill 包的上传、下载和版本管理

提供 Skill 包（zip）的存储、SHA-256 校验和计算、版本历史管理。
Skill 包存储在 data/skill_store/{skill_name}/{version}/ 目录下。
"""

import hashlib
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from control_plane.database import get_connection

# Skill 包存储根目录
SKILL_STORE_DIR = Path("data/skill_store")


def _ensure_store_dir() -> None:
    """确保 Skill Store 存储目录存在"""
    SKILL_STORE_DIR.mkdir(parents=True, exist_ok=True)


def compute_sha256(data: bytes) -> str:
    """计算 SHA-256 校验和"""
    return hashlib.sha256(data).hexdigest()


async def upload_skill_package(name: str, file_data: bytes) -> dict:
    """上传 Skill 包（zip），计算校验和并存储

    如果 Skill 已存在则递增版本号，否则创建新记录。

    Args:
        name: Skill 名称
        file_data: zip 文件的二进制内容

    Returns:
        包含 skill 信息和版本详情的字典
    """
    _ensure_store_dir()
    checksum = compute_sha256(file_data)
    file_size = len(file_data)
    now = datetime.now(timezone.utc).isoformat()

    conn = await get_connection()
    try:
        # 查找或创建 skill_registry 记录
        cursor = await conn.execute(
            "SELECT id, version FROM skill_registry WHERE name = ?", (name,)
        )
        row = await cursor.fetchone()

        if row:
            skill_id = row[0]
            new_version = row[1] + 1
            # 更新 skill_registry
            await conn.execute(
                """UPDATE skill_registry
                   SET version = ?, checksum = ?, file_size = ?, uploaded_at = ?
                   WHERE id = ?""",
                (new_version, checksum, file_size, now, skill_id),
            )
        else:
            skill_id = str(uuid.uuid4())
            new_version = 1
            await conn.execute(
                """INSERT INTO skill_registry
                   (id, name, description, source, version, checksum, file_size, uploaded_at, created_at)
                   VALUES (?, ?, '', 'custom', ?, ?, ?, ?, ?)""",
                (skill_id, name, new_version, checksum, file_size, now, now),
            )

        # 存储文件到磁盘
        pkg_dir = SKILL_STORE_DIR / name / str(new_version)
        pkg_dir.mkdir(parents=True, exist_ok=True)
        pkg_path = pkg_dir / f"{name}.zip"
        pkg_path.write_bytes(file_data)

        # 更新 skill_registry 的 package_path
        rel_path = str(pkg_path)
        await conn.execute(
            "UPDATE skill_registry SET package_path = ? WHERE id = ?",
            (rel_path, skill_id),
        )

        # 创建 skill_packages 版本记录
        pkg_id = str(uuid.uuid4())
        await conn.execute(
            """INSERT INTO skill_packages
               (id, skill_id, version, checksum, package_path, file_size, uploaded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (pkg_id, skill_id, new_version, checksum, rel_path, file_size, now),
        )

        await conn.commit()

        return {
            "skill_id": skill_id,
            "name": name,
            "version": new_version,
            "checksum": checksum,
            "file_size": file_size,
            "package_path": rel_path,
            "uploaded_at": now,
        }
    finally:
        await conn.close()


async def download_skill_package(name: str, version: int | None = None) -> tuple[bytes, dict] | None:
    """下载 Skill 包

    Args:
        name: Skill 名称
        version: 指定版本号，None 则下载最新版本

    Returns:
        (文件内容, 元数据字典) 或 None（不存在时）
    """
    conn = await get_connection()
    try:
        if version is not None:
            cursor = await conn.execute(
                """SELECT sp.package_path, sp.version, sp.checksum, sp.file_size, sp.uploaded_at
                   FROM skill_packages sp
                   JOIN skill_registry sr ON sp.skill_id = sr.id
                   WHERE sr.name = ? AND sp.version = ?""",
                (name, version),
            )
        else:
            # 最新版本
            cursor = await conn.execute(
                """SELECT sp.package_path, sp.version, sp.checksum, sp.file_size, sp.uploaded_at
                   FROM skill_packages sp
                   JOIN skill_registry sr ON sp.skill_id = sr.id
                   WHERE sr.name = ?
                   ORDER BY sp.version DESC LIMIT 1""",
                (name,),
            )

        row = await cursor.fetchone()
        if not row:
            return None

        pkg_path = Path(row[0])
        if not pkg_path.exists():
            return None

        file_data = pkg_path.read_bytes()
        meta = {
            "name": name,
            "version": row[1],
            "checksum": row[2],
            "file_size": row[3],
            "uploaded_at": row[4],
        }
        return file_data, meta
    finally:
        await conn.close()


async def get_skill_versions(name: str) -> list[dict]:
    """查询 Skill 的版本历史

    Args:
        name: Skill 名称

    Returns:
        版本列表，按版本号降序排列
    """
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            """SELECT sp.id, sp.version, sp.checksum, sp.file_size, sp.uploaded_at
               FROM skill_packages sp
               JOIN skill_registry sr ON sp.skill_id = sr.id
               WHERE sr.name = ?
               ORDER BY sp.version DESC""",
            (name,),
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": row[0],
                "version": row[1],
                "checksum": row[2],
                "file_size": row[3],
                "uploaded_at": row[4],
            }
            for row in rows
        ]
    finally:
        await conn.close()


async def delete_skill_package(name: str, version: int | None = None) -> bool:
    """删除 Skill 包

    Args:
        name: Skill 名称
        version: 指定版本号，None 则删除所有版本

    Returns:
        是否成功删除
    """
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id FROM skill_registry WHERE name = ?", (name,)
        )
        row = await cursor.fetchone()
        if not row:
            return False

        skill_id = row[0]

        if version is not None:
            await conn.execute(
                "DELETE FROM skill_packages WHERE skill_id = ? AND version = ?",
                (skill_id, version),
            )
            # 删除磁盘文件
            pkg_dir = SKILL_STORE_DIR / name / str(version)
            if pkg_dir.exists():
                shutil.rmtree(pkg_dir)
        else:
            await conn.execute(
                "DELETE FROM skill_packages WHERE skill_id = ?", (skill_id,)
            )
            # 删除整个 Skill 目录
            skill_dir = SKILL_STORE_DIR / name
            if skill_dir.exists():
                shutil.rmtree(skill_dir)

        await conn.commit()
        return True
    finally:
        await conn.close()
