"""更新管理 API"""

import hashlib
import zipfile
from pathlib import Path
from datetime import datetime, timezone

from quart import Blueprint, request, send_file, jsonify

from control_plane.auth import require_auth
from control_plane.database import get_connection

bp = Blueprint("updates", __name__, url_prefix="/api/updates")

# 更新包存储目录
UPDATES_DIR = Path("control_plane/data/updates")
UPDATES_DIR.mkdir(parents=True, exist_ok=True)


@bp.route("/upload", methods=["POST"])
@require_auth(role="admin")
async def upload_update():
    """上传更新包"""
    files = await request.files
    if "file" not in files:
        return jsonify({"error": "No file provided"}), 400
    
    file = files["file"]
    form = await request.form
    version = form.get("version", "unknown")
    description = form.get("description", "")
    
    # 保存文件
    filename = f"nanobot-update-{version}.zip"
    file_path = UPDATES_DIR / filename
    await file.save(file_path)
    
    # 计算文件哈希
    file_hash = hashlib.md5(file_path.read_bytes()).hexdigest()
    file_size = file_path.stat().st_size
    
    # 保存到数据库
    conn = await get_connection()
    try:
        now = datetime.now(timezone.utc).isoformat()
        await conn.execute(
            """INSERT INTO updates (version, filename, file_hash, file_size, description, uploaded_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (version, filename, file_hash, file_size, description, now)
        )
        await conn.commit()
    finally:
        await conn.close()
    
    return jsonify({
        "version": version,
        "filename": filename,
        "file_hash": file_hash,
        "file_size": file_size
    })


@bp.route("/list", methods=["GET"])
@require_auth()
async def list_updates():
    """列出所有更新包"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT version, filename, file_hash, file_size, description, uploaded_at "
            "FROM updates ORDER BY uploaded_at DESC"
        )
        rows = await cursor.fetchall()
        return jsonify([{
            "version": row[0],
            "filename": row[1],
            "file_hash": row[2],
            "file_size": row[3],
            "description": row[4],
            "uploaded_at": row[5]
        } for row in rows])
    finally:
        await conn.close()


@bp.route("/download/<version>", methods=["GET"])
@require_auth()
async def download_update(version: str):
    """下载更新包"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT filename FROM updates WHERE version = ?",
            (version,)
        )
        row = await cursor.fetchone()
        if not row:
            return jsonify({"error": "Update not found"}), 404
        
        filename = row[0]
        file_path = UPDATES_DIR / filename
        
        if not file_path.exists():
            return jsonify({"error": "File not found"}), 404
        
        return await send_file(file_path, as_attachment=True, attachment_filename=filename)
    finally:
        await conn.close()


@bp.route("/check", methods=["GET"])
@require_auth()
async def check_update():
    """检查是否有新版本"""
    current_version = request.args.get("current_version", "0.0.0")
    
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT version, filename, file_hash, file_size, description "
            "FROM updates ORDER BY uploaded_at DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        
        if not row:
            return jsonify({"has_update": False})
        
        latest_version = row[0]
        
        # 简单版本比较（可以改进）
        has_update = latest_version != current_version
        
        return jsonify({
            "has_update": has_update,
            "latest_version": latest_version,
            "filename": row[1],
            "file_hash": row[2],
            "file_size": row[3],
            "description": row[4]
        })
    finally:
        await conn.close()
