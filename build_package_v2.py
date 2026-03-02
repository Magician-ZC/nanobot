#!/usr/bin/env python3
"""
Nanobot Agent Node Windows 打包脚本 (简化版)
在 Mac/Linux 上运行，生成可在 Windows 上安装的压缩包
"""

import os
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

# 配置
PACKAGE_NAME = "nanobot-agent-node-windows"
PACKAGE_VERSION = "0.1.4"
BUILD_DIR = Path("build")
DIST_DIR = Path("dist")
TEMP_DIR = BUILD_DIR / f"{PACKAGE_NAME}-{PACKAGE_VERSION}"

# 颜色输出
class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'

def print_status(message, status="info"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    if status == "success":
        print(f"[{timestamp}] {Colors.GREEN}✓{Colors.END} {message}")
    elif status == "error":
        print(f"[{timestamp}] {Colors.RED}✗{Colors.END} {message}")
    elif status == "warning":
        print(f"[{timestamp}] {Colors.YELLOW}⚠{Colors.END} {message}")
    else:
        print(f"[{timestamp}] {Colors.CYAN}ℹ{Colors.END} {message}")

def print_header(title):
    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print(f"║ {title.center(58)} ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()

def clean_build_dirs():
    """清理旧的构建目录"""
    print_status("清理旧的构建目录...")
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)

    BUILD_DIR.mkdir(exist_ok=True)
    DIST_DIR.mkdir(exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    print_status("创建构建目录", "success")

def copy_nanobot_source():
    """复制 nanobot 源代码"""
    print_status("复制 nanobot 源代码...")
    src = Path("nanobot")
    dst = TEMP_DIR / "nanobot"

    if not src.exists():
        print_status("nanobot 目录不存在", "error")
        return False

    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
        '__pycache__', '*.pyc', '.pytest_cache', '.git', '*.egg-info'
    ))
    print_status("源代码复制完成", "success")
    return True

def copy_project_files():
    """复制项目配置文件"""
    print_status("复制项目配置文件...")

    files_to_copy = [
        "pyproject.toml",
        "README.md",
        "LICENSE",
    ]

    for file in files_to_copy:
        src = Path(file)
        if src.exists():
            shutil.copy(src, TEMP_DIR / file)

    print_status("项目配置复制完成", "success")

def copy_bridge():
    """复制 bridge 目录"""
    print_status("复制 bridge 目录...")
    src = Path("bridge")
    dst = TEMP_DIR / "bridge"

    if src.exists():
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
            '__pycache__', '*.pyc', 'node_modules', '.git', 'dist', 'build'
        ))
        print_status("bridge 目录复制完成", "success")
    else:
        print_status("bridge 目录不存在，跳过", "warning")

def generate_requirements():
    """生成 requirements.txt"""
    print_status("生成依赖列表...")

    requirements = """typer>=0.20.0,<1.0.0
litellm>=1.81.5,<2.0.0
pydantic>=2.12.0,<3.0.0
pydantic-settings>=2.12.0,<3.0.0
websockets>=16.0,<17.0
websocket-client>=1.9.0,<2.0.0
httpx>=0.28.0,<1.0.0
oauth-cli-kit>=0.1.3,<1.0.0
loguru>=0.7.3,<1.0.0
readability-lxml>=0.8.4,<1.0.0
rich>=14.0.0,<15.0.0
croniter>=6.0.0,<7.0.0
dingtalk-stream>=0.24.0,<1.0.0
python-telegram-bot[socks]>=22.0,<23.0
lark-oapi>=1.5.0,<2.0.0
socksio>=1.0.0,<2.0.0
python-socketio>=5.16.0,<6.0.0
msgpack>=1.1.0,<2.0.0
slack-sdk>=3.39.0,<4.0.0
slackify-markdown>=0.2.0,<1.0.0
qq-botpy>=1.2.0,<2.0.0
python-socks[asyncio]>=2.8.0,<3.0.0
prompt-toolkit>=3.0.50,<4.0.0
mcp>=1.26.0,<2.0.0
json-repair>=0.57.0,<1.0.0
"""

    (TEMP_DIR / "requirements.txt").write_text(requirements)
    print_status("依赖列表生成完成", "success")

def create_install_bat():
    """创建 Windows 安装脚本 (Batch)"""
    print_status("创建安装脚本...")

    install_bat = """@echo off
REM Nanobot Agent Node Installation Script
REM Run this script to install nanobot

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo     Nanobot Agent Node Installation
echo ============================================================
echo.

REM Check Python
echo [*] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    echo Please install Python 3.11+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

REM Create virtual environment
set VENV_PATH=%USERPROFILE%\\nanobot\\.venv
if not exist "%VENV_PATH%" (
    echo [*] Creating virtual environment...
    python -m venv "%VENV_PATH%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment already exists
)

REM Activate virtual environment
echo [*] Activating virtual environment...
call "%VENV_PATH%\\Scripts\\activate.bat"

REM Upgrade pip
echo [*] Upgrading pip...
python -m pip install --upgrade pip setuptools wheel >nul 2>&1

REM Install requirements
echo [*] Installing dependencies (this may take a few minutes)...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo [OK] Dependencies installed

REM Install nanobot from source
echo [*] Installing nanobot from source...
pip install -e .
if errorlevel 1 (
    echo [ERROR] Failed to install nanobot
    pause
    exit /b 1
)
echo [OK] Nanobot installed

REM Initialize nanobot
echo [*] Initializing nanobot...
nanobot onboard
if errorlevel 1 (
    echo [ERROR] Failed to initialize nanobot
    pause
    exit /b 1
)
echo [OK] Nanobot initialized

echo.
echo ============================================================
echo                 Installation Complete!
echo ============================================================
echo.
echo Next steps:
echo   1. Edit config file: %%USERPROFILE%%.nanobot\\config.json
echo      - Add LLM Provider API Key (e.g., OpenRouter)
echo.
echo   2. Start Agent Node:
echo      - Run: start.bat
echo      - Or: nanobot gateway
echo.
echo   3. Register to Control Plane (optional):
echo      - Run: nanobot register --token token_xxx --server http://cp-host:8080
echo.

pause
"""

    (TEMP_DIR / "install.bat").write_text(install_bat)
    print_status("安装脚本创建完成", "success")

def create_start_bat():
    """创建启动脚本"""
    print_status("创建启动脚本...")

    start_bat = """@echo off
REM Nanobot Agent Node Startup Script

setlocal enabledelayedexpansion

set VENV_PATH=%USERPROFILE%\\nanobot\\.venv
set ACTIVATE_SCRIPT=!VENV_PATH!\\Scripts\\activate.bat

if not exist "!ACTIVATE_SCRIPT!" (
    echo [ERROR] Virtual environment not found
    echo Please run install.bat first
    pause
    exit /b 1
)

echo [*] Activating virtual environment...
call "!ACTIVATE_SCRIPT!"

echo [*] Starting Nanobot Gateway...
echo.
nanobot gateway

pause
"""

    (TEMP_DIR / "start.bat").write_text(start_bat)
    print_status("启动脚本创建完成", "success")

def create_readme():
    """创建详细说明"""
    print_status("创建安装说明...")

    readme = f"""# Nanobot Agent Node Windows Installation Package

Version: {PACKAGE_VERSION}

## Quick Start

### Step 1: Install Python

1. Download Python 3.11+: https://www.python.org/downloads/
2. Run the installer
3. **IMPORTANT**: Check "Add Python to PATH"
4. Complete installation

Verify: Open cmd or PowerShell, run:
```
python --version
```

### Step 2: Run Installation Script

**Option A: Double-click install.bat (Easiest)**
- Double-click `install.bat`
- Wait for installation to complete
- Press Enter to exit

**Option B: Run from PowerShell**
```powershell
.\\install.bat
```

**Option C: Run from Command Prompt**
```cmd
install.bat
```

### Step 3: Configure

Edit `%USERPROFILE%\.nanobot\config.json`:

```json
{{
  "providers": {{
    "openrouter": {{
      "apiKey": "sk-or-v1-xxx"
    }}
  }},
  "agents": {{
    "defaults": {{
      "model": "anthropic/claude-opus-4-5"
    }}
  }}
}}
```

Get API Key:
- OpenRouter: https://openrouter.ai/keys
- Anthropic: https://console.anthropic.com
- OpenAI: https://platform.openai.com

### Step 4: Start

**Option A: Double-click start.bat (Easiest)**
- Double-click `start.bat`

**Option B: Run from PowerShell**
```powershell
.\\start.bat
```

### Step 5: Register to Control Plane (Optional)

If you have a Control Plane server:

```powershell
$venv = "$env:USERPROFILE\nanobot\.venv\Scripts\Activate.ps1"
& $venv
nanobot register --token token_xxx --server http://cp-host:8080
```

## Files

| File | Description |
|------|-------------|
| `install.bat` | Installation script (run this first) |
| `start.bat` | Startup script (run this to start) |
| `nanobot/` | Nanobot source code |
| `requirements.txt` | Python dependencies |
| `pyproject.toml` | Project configuration |
| `README.md` | Project documentation |

## Troubleshooting

### Python not found

Error:
```
'python' is not recognized as an internal or external command
```

Solution:
1. Make sure Python is installed
2. Restart PowerShell or cmd
3. Check: `python --version`

### Installation fails

1. Check internet connection
2. Try running install.bat again
3. Check logs: `%USERPROFILE%\.nanobot\logs\nanobot.log`

### Cannot run .bat files

If you get permission errors:
1. Right-click install.bat
2. Select "Run as administrator"

## Support

- Documentation: https://github.com/HKUDS/nanobot
- Issues: https://github.com/HKUDS/nanobot/issues
- Discussions: https://github.com/HKUDS/nanobot/discussions

---

Enjoy using Nanobot! 🚀
"""

    (TEMP_DIR / "README_INSTALL.md").write_text(readme)
    print_status("安装说明创建完成", "success")

def create_zip():
    """创建 ZIP 压缩包"""
    print_status("创建压缩包...")

    zip_path = DIST_DIR / f"{PACKAGE_NAME}-{PACKAGE_VERSION}.zip"

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(TEMP_DIR):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(BUILD_DIR)
                zipf.write(file_path, arcname)

    if zip_path.exists():
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        print_status(f"压缩包创建成功 ({size_mb:.2f} MB)", "success")
        return zip_path
    else:
        print_status("压缩包创建失败", "error")
        return None

def count_files(path):
    """计算文件数量"""
    count = 0
    for root, dirs, files in os.walk(path):
        count += len(files)
    return count

def main():
    print_header("Nanobot Agent Node Windows Package Builder")

    try:
        # 清理
        clean_build_dirs()

        # 复制文件
        if not copy_nanobot_source():
            return

        copy_project_files()
        copy_bridge()

        # 生成文件
        generate_requirements()
        create_install_bat()
        create_start_bat()
        create_readme()

        # 打包
        zip_path = create_zip()

        if zip_path:
            file_count = count_files(TEMP_DIR)

            print()
            print("╔════════════════════════════════════════════════════════════╗")
            print("║                    Build Complete!                         ║")
            print("╚════════════════════════════════════════════════════════════╝")
            print()

            print_status(f"Package: {PACKAGE_NAME}-{PACKAGE_VERSION}.zip", "info")
            print_status(f"Location: {zip_path}", "info")
            print_status(f"Files: {file_count}", "info")

            print()
            print("Next steps:")
            print(f"  1. Copy the zip file to target Windows PC")
            print(f"  2. Extract the zip file")
            print(f"  3. Double-click install.bat")
            print(f"  4. Wait for installation to complete")
            print(f"  5. Edit config.json and add Control Plane info")
            print(f"  6. Double-click start.bat to start")
            print()

    except Exception as e:
        print_status(f"Build failed: {e}", "error")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()
