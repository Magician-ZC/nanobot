#!/usr/bin/env python3
"""
Nanobot Agent Node Windows 打包脚本
在 Mac/Linux 上运行，生成可在 Windows 上安装的压缩包
"""

import os
import shutil
import zipfile
import json
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
        "deploy_agent_node.ps1",
        "AGENT_NODE_DEPLOYMENT.md",
    ]

    for file in files_to_copy:
        src = Path(file)
        if src.exists():
            shutil.copy(src, TEMP_DIR / file)

    print_status("项目配置复制完成", "success")

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

def create_install_script():
    """创建 Windows 安装脚本"""
    print_status("创建安装脚本...")

    install_script = r'''# Nanobot Agent Node 安装脚本
# 这个脚本会自动安装 nanobot 并初始化配置

$ErrorActionPreference = "Stop"

function Write-Status {
    param([string]$Message, [string]$Type = "Info")
    $timestamp = Get-Date -Format "HH:mm:ss"
    switch ($Type) {
        "Success" { Write-Host "[$timestamp] ✓ $Message" -ForegroundColor Green }
        "Error" { Write-Host "[$timestamp] ✗ $Message" -ForegroundColor Red }
        "Warning" { Write-Host "[$timestamp] ⚠ $Message" -ForegroundColor Yellow }
        default { Write-Host "[$timestamp] ℹ $Message" -ForegroundColor Cyan }
    }
}

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     Nanobot Agent Node 安装程序                           ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# 检查 Python
Write-Status "检查 Python..."
try {
    $version = python --version 2>&1
    Write-Status "检测到 Python: $version" "Success"
} catch {
    Write-Status "Python 未安装，请先安装 Python 3.11+" "Error"
    Write-Host "下载地址: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "安装时请勾选 'Add Python to PATH'" -ForegroundColor Yellow
    Read-Host "按 Enter 键退出"
    exit 1
}

# 创建虚拟环境
$venvPath = "$env:USERPROFILE\nanobot\.venv"
if (-not (Test-Path $venvPath)) {
    Write-Status "创建虚拟环境..."
    python -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Status "虚拟环境创建失败" "Error"
        Read-Host "按 Enter 键退出"
        exit 1
    }
    Write-Status "虚拟环境创建成功" "Success"
} else {
    Write-Status "虚拟环境已存在" "Info"
}

# 激活虚拟环境
$activateScript = "$venvPath\Scripts\Activate.ps1"
Write-Status "激活虚拟环境..."
& $activateScript

# 升级 pip
Write-Status "升级 pip..."
python -m pip install --upgrade pip setuptools wheel 2>&1 | Out-Null

# 安装依赖
Write-Status "安装依赖包（这可能需要几分钟）..."
$requirementsPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$requirementsFile = Join-Path $requirementsPath "requirements.txt"

if (Test-Path $requirementsFile) {
    pip install -r $requirementsFile
} else {
    Write-Status "requirements.txt 未找到，使用 pip 直接安装 nanobot-ai" "Warning"
    pip install nanobot-ai
}

if ($LASTEXITCODE -ne 0) {
    Write-Status "依赖安装失败" "Error"
    Read-Host "按 Enter 键退出"
    exit 1
}
Write-Status "依赖安装成功" "Success"

# 初始化 nanobot
Write-Status "初始化 nanobot..."
nanobot onboard
Write-Status "初始化完成" "Success"

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                    安装完成！                              ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

Write-Status "后续步骤:" "Info"
Write-Host "  1. 编辑配置文件: $env:USERPROFILE\.nanobot\config.json"
Write-Host "     - 添加 LLM Provider API Key（如 OpenRouter）"
Write-Host ""
Write-Host "  2. 启动 Agent Node:"
Write-Host "     - 方式 A: 双击 start.bat"
Write-Host "     - 方式 B: 在 PowerShell 中运行:"
Write-Host "       & '$activateScript'"
Write-Host "       nanobot gateway"
Write-Host ""
Write-Host "  3. 注册到 Control Plane（可选）:"
Write-Host "     - 获取注册令牌（从 Control Plane 管理界面）"
Write-Host "     - 运行: nanobot register --token token_xxx --server http://cp-host:8080"
Write-Host ""
Write-Host "  4. 查看日志:"
Write-Host "     - Get-Content $env:USERPROFILE\.nanobot\logs\nanobot.log -Tail 50 -Wait"
Write-Host ""

Read-Host "按 Enter 键退出"
'''

    (TEMP_DIR / "install.ps1").write_text(install_script)
    print_status("安装脚本创建完成", "success")

def create_start_script():
    """创建 Windows 快速启动脚本"""
    print_status("创建快速启动脚本...")

    # 创建 PowerShell 启动脚本（更可靠）
    start_ps1 = r'''# Nanobot Agent Node 启动脚本

$venvPath = "$env:USERPROFILE\nanobot\.venv"
$activateScript = "$venvPath\Scripts\Activate.ps1"

if (-not (Test-Path $activateScript)) {
    Write-Host "[ERROR] Virtual environment not found" -ForegroundColor Red
    Write-Host "Please run install.ps1 first" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[*] Activating virtual environment..." -ForegroundColor Cyan
& $activateScript

Write-Host "[*] Starting Nanobot Gateway..." -ForegroundColor Cyan
Write-Host ""
nanobot gateway
'''

    (TEMP_DIR / "start.ps1").write_text(start_ps1)

    # 创建简单的 bat 文件来启动 PowerShell 脚本
    start_bat = r'''@echo off
REM Nanobot Agent Node Startup Script
REM This script launches the PowerShell startup script

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set PS_SCRIPT=%SCRIPT_DIR%start.ps1

if not exist "%PS_SCRIPT%" (
    echo [ERROR] start.ps1 not found
    pause
    exit /b 1
)

echo [*] Starting Nanobot...
powershell -ExecutionPolicy Bypass -File "%PS_SCRIPT%"
pause
'''

    (TEMP_DIR / "start.bat").write_text(start_bat)
    print_status("快速启动脚本创建完成", "success")

def create_install_md():
    """创建详细安装说明"""
    print_status("创建安装说明...")

    install_md = f"""# Nanobot Agent Node Windows 安装包

版本: {PACKAGE_VERSION}

## 快速开始

### 第一步：安装 Python

1. 下载 Python 3.11+: https://www.python.org/downloads/
2. 运行安装程序
3. **重要**：勾选 "Add Python to PATH"
4. 完成安装

验证安装：打开 cmd 或 PowerShell，运行：
```
python --version
```

### 第二步：运行安装脚本

**方式 A：使用 PowerShell（推荐）**

1. 右键点击 `install.ps1`
2. 选择 "使用 PowerShell 运行"
3. 如果提示权限错误，运行：
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope CurrentUser
   ```
   然后重新运行 `install.ps1`

**方式 B：手动安装**

1. 打开 PowerShell
2. 进入解压目录
3. 运行：
   ```powershell
   powershell -ExecutionPolicy Bypass -File install.ps1
   ```

### 第三步：配置

编辑 `%USERPROFILE%\.nanobot\config.json`：

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

获取 API Key：
- OpenRouter: https://openrouter.ai/keys
- Anthropic: https://console.anthropic.com
- OpenAI: https://platform.openai.com

### 第四步：启动

**方式 A：双击启动**
- 双击 `start.bat`

**方式 B：手动启动**
```powershell
$venv = "$env:USERPROFILE\nanobot\.venv\Scripts\Activate.ps1"
& $venv
nanobot gateway
```

### 第五步：注册到 Control Plane（可选）

如果你有 Control Plane 中控服务器：

1. 从 Control Plane 管理界面获取注册令牌
2. 在 PowerShell 中运行：
   ```powershell
   $venv = "$env:USERPROFILE\nanobot\.venv\Scripts\Activate.ps1"
   & $venv
   nanobot register --token token_xxx --server http://cp-host:8080
   ```

## 文件说明

| 文件 | 说明 |
|------|------|
| `install.ps1` | 自动安装脚本（推荐使用） |
| `start.bat` | 快速启动脚本 |
| `nanobot/` | nanobot 源代码 |
| `requirements.txt` | Python 依赖列表 |
| `AGENT_NODE_DEPLOYMENT.md` | 详细部署指南 |
| `INSTALL.md` | 本文件 |

## 故障排查

### 问题 1：无法运行 PowerShell 脚本

**错误信息**：
```
cannot be loaded because running scripts is disabled on this system
```

**解决方案**：
```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope CurrentUser
```

### 问题 2：Python 未找到

**错误信息**：
```
'python' is not recognized as an internal or external command
```

**解决方案**：
1. 确保 Python 已安装
2. 重启 PowerShell 或 cmd
3. 检查 Python 是否添加到 PATH：
   ```powershell
   python --version
   ```

### 问题 3：依赖安装失败

**错误信息**：
```
ERROR: Could not find a version that satisfies the requirement
```

**解决方案**：
1. 检查网络连接
2. 尝试手动安装：
   ```powershell
   $venv = "$env:USERPROFILE\nanobot\.venv\Scripts\Activate.ps1"
   & $venv
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

## 常见问题

**Q: 如何更新 nanobot？**

A: 在虚拟环境中运行：
```powershell
pip install --upgrade nanobot-ai
```

**Q: 如何卸载？**

A: 删除以下目录：
```powershell
Remove-Item -Recurse $env:USERPROFILE\.nanobot
Remove-Item -Recurse $env:USERPROFILE\nanobot
```

**Q: 如何开机自启？**

A: 创建 Windows 计划任务：
```powershell
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File C:\\path\\to\\start.bat"
$trigger = New-ScheduledTaskTrigger -AtStartup
Register-ScheduledTask -TaskName "NanobotAgentNode" -Action $action -Trigger $trigger -Force
```

## 支持

- 文档：https://github.com/HKUDS/nanobot
- 问题反馈：https://github.com/HKUDS/nanobot/issues
- 讨论：https://github.com/HKUDS/nanobot/discussions

---

祝你使用愉快！🚀
"""

    (TEMP_DIR / "INSTALL.md").write_text(install_md)
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
    print_header("Nanobot Agent Node Windows 打包脚本")

    try:
        # 清理
        clean_build_dirs()

        # 复制文件
        if not copy_nanobot_source():
            return

        copy_project_files()

        # 生成文件
        generate_requirements()
        create_install_script()
        create_start_script()
        create_install_md()

        # 打包
        zip_path = create_zip()

        if zip_path:
            file_count = count_files(TEMP_DIR)

            print()
            print("╔════════════════════════════════════════════════════════════╗")
            print("║                    打包完成！                              ║")
            print("╚════════════════════════════════════════════════════════════╝")
            print()

            print_status(f"包名: {PACKAGE_NAME}-{PACKAGE_VERSION}.zip", "info")
            print_status(f"位置: {zip_path}", "info")
            print_status(f"文件数: {file_count}", "info")

            print()
            print("下一步:")
            print(f"  1. 将压缩包复制到目标 Windows 电脑")
            print(f"  2. 解压缩")
            print(f"  3. 运行 install.ps1")
            print()

    except Exception as e:
        print_status(f"打包失败: {e}", "error")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()
