"""Skill Store API 路由 - Skill 包的上传、下载和版本管理"""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import Response

from control_plane.auth import get_current_user, require_admin
from control_plane.skill_store import (
    download_skill_package,
    get_skill_versions,
    upload_skill_package,
)

router = APIRouter()


@router.post("/api/skills/{name}/upload", status_code=status.HTTP_201_CREATED)
async def upload_skill(
    name: str,
    file: UploadFile,
    _admin: dict = Depends(require_admin),
):
    """上传 Skill 包（zip），计算 SHA-256 校验和（仅 admin）"""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .zip files are accepted",
        )

    file_data = await file.read()
    if not file_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )

    result = await upload_skill_package(name, file_data)
    return result


@router.get("/api/skills/{name}/download")
async def download_skill(
    name: str,
    version: int | None = Query(default=None, description="版本号，不指定则下载最新版"),
    _user: dict = Depends(get_current_user),
):
    """下载 Skill 包"""
    result = await download_skill_package(name, version)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill package '{name}' not found",
        )

    file_data, meta = result
    return Response(
        content=file_data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{name}-v{meta["version"]}.zip"',
            "X-Checksum-SHA256": meta["checksum"],
            "X-Skill-Version": str(meta["version"]),
        },
    )


@router.get("/api/skills/{name}/versions")
async def list_skill_versions(
    name: str,
    _user: dict = Depends(get_current_user),
):
    """查询 Skill 版本历史"""
    versions = await get_skill_versions(name)
    if not versions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{name}' not found or has no packages",
        )
    return {"name": name, "versions": versions}
