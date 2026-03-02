#!/usr/bin/env python3
"""
创建增量更新包
只打包修改过的文件，节点可以直接覆盖更新
"""

import hashlib
import json
import zipfile
from pathlib import Path
from datetime import datetime

# 配置
UPDATE_VERSION = "0.1.5"  # 更新版本号
DIST_DIR = Path("dist")
UPDATE_DIR = DIST_DIR / f"update-{UPDATE_VERSION}"

# 需要打包的文件/目录
FILES_TO_PACKAGE = [
    "nanobot/",  # 整个 nanobot 目录
    "pyproject.toml",
]

def calculate_file_hash(file_path):
    """计算文件 MD5"""
    md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5.update(chunk)
    return md5.hexdigest()

def create_update_package():
    """创建更新包"""
    print(f"📦 创建更新包 v{UPDATE_VERSION}...")
    
    # 创建目录
    UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    
    # 收集文件
    files_to_zip = []
    file_manifest = {}
    
    for item in FILES_TO_PACKAGE:
        path = Path(item)
        if path.is_dir():
            # 递归收集目录中的文件
            for file_path in path.rglob("*"):
                if file_path.is_file() and not any(
                    p in file_path.parts for p in ["__pycache__", ".pyc", ".pytest_cache", ".git"]
                ):
                    files_to_zip.append(file_path)
                    file_manifest[str(file_path)] = calculate_file_hash(file_path)
        elif path.is_file():
            files_to_zip.append(path)
            file_manifest[str(path)] = calculate_file_hash(path)
    
    # 创建 manifest.json
    manifest = {
        "version": UPDATE_VERSION,
        "created_at": datetime.now().isoformat(),
        "files": file_manifest,
        "total_files": len(files_to_zip)
    }
    
    manifest_path = UPDATE_DIR / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    # 先创建 update.bat（使用 GBK 编码以兼容 Windows）
    update_bat_content = create_update_bat_content()
    update_bat_path = UPDATE_DIR / "update.bat"
    with open(update_bat_path, 'w', encoding='gbk') as f:
        f.write(update_bat_content)
    
    # 创建 ZIP
    zip_path = DIST_DIR / f"nanobot-update-{UPDATE_VERSION}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # 添加 manifest
        zipf.write(manifest_path, "manifest.json")
        
        # 添加 update.bat
        zipf.write(update_bat_path, "update.bat")
        
        # 添加所有文件
        for file_path in files_to_zip:
            zipf.write(file_path, file_path)
    
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"✅ 更新包创建成功: {zip_path}")
    print(f"   文件数: {len(files_to_zip) + 1}")  # +1 for update.bat
    print(f"   大小: {size_mb:.2f} MB")
    
    return zip_path

def create_update_bat_content():
    """生成 Windows 更新脚本内容"""
    return f"""@echo off
REM Nanobot Auto Update Script v{UPDATE_VERSION}

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo     Nanobot Auto Update v{UPDATE_VERSION}
echo ============================================================
echo.

REM Check update package
if not exist "nanobot-update-{UPDATE_VERSION}.zip" (
    echo [ERROR] Update package not found: nanobot-update-{UPDATE_VERSION}.zip
    pause
    exit /b 1
)

REM Stop nanobot if running
echo [*] Stopping nanobot service...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq nanobot*" >nul 2>&1

REM Backup current version
echo [*] Backing up current version...
set BACKUP_DIR=backup_%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set BACKUP_DIR=!BACKUP_DIR: =0!
mkdir "!BACKUP_DIR!" 2>nul
xcopy /E /I /Y nanobot "!BACKUP_DIR!\\nanobot" >nul 2>&1
echo [OK] Backup completed: !BACKUP_DIR!

REM Extract update package
echo [*] Extracting update package...
powershell -Command "Expand-Archive -Path 'nanobot-update-{UPDATE_VERSION}.zip' -DestinationPath '.' -Force"
if errorlevel 1 (
    echo [ERROR] Extraction failed
    pause
    exit /b 1
)
echo [OK] Extraction completed

REM Reinstall
echo [*] Reinstalling nanobot...
set VENV_PATH=%USERPROFILE%\\nanobot\\.venv
call "!VENV_PATH!\\Scripts\\activate.bat"
pip install -e . --quiet
if errorlevel 1 (
    echo [ERROR] Installation failed
    echo [*] Restoring backup...
    xcopy /E /I /Y "!BACKUP_DIR!\\nanobot" nanobot >nul 2>&1
    pause
    exit /b 1
)
echo [OK] Installation completed

echo.
echo ============================================================
echo                 Update Completed!
echo ============================================================
echo.
echo Update version: v{UPDATE_VERSION}
echo Backup location: !BACKUP_DIR!
echo.
echo Please run start.bat to start nanobot
echo.

pause
"""

if __name__ == "__main__":
    create_update_package()
    
    print()
    print("📋 使用说明:")
    print(f"  1. 将 dist/nanobot-update-{UPDATE_VERSION}.zip 复制到目标电脑")
    print(f"  2. 解压 ZIP 文件")
    print(f"  3. 将解压出的所有文件放到 nanobot 安装目录（和 start.bat 同级）")
    print(f"  4. 双击运行 update.bat")
    print()
