#!/usr/bin/env pwsh
# Nanobot Agent Node Windows 打包脚本
# 用途：将 nanobot 打包成可直接安装的压缩包
# 运行：pwsh build_package.ps1 或 powershell -ExecutionPolicy Bypass -File build_package.ps1

param(
    [string]$OutputDir = "dist",
    [string]$BuildDir = "build"
)

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

# 读取版本
$pyprojectPath = "pyproject.toml"
$version = "0.1.4"
if (Test-Path $pyprojectPath) {
    $content = Get-Content $pyprojectPath -Raw
    if ($content -match 'version = "([^"]+)"') {
        $version = $matches[1]
    }
}

$PACKAGE_NAME = "nanobot-agent-node-windows"
$PACKAGE_VERSION = $version
$TEMP_DIR = Join-Path $BuildDir "$PACKAGE_NAME-$PACKAGE_VERSION"
$ZIP_FILE = Join-Path $OutputDir "$PACKAGE_NAME-$PACKAGE_VERSION.zip"

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     Nanobot Agent Node Windows 打包脚本                   ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# 清理旧的构建目录
if (Test-Path $BuildDir) {
    Write-Status "清理旧的构建目录..."
    Remove-Item -Recurse -Force $BuildDir
}
if (Test-Path $OutputDir) {
    Remove-Item -Recurse -Force $OutputDir
}

New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
New-Item -ItemType Directory -Path $TEMP_DIR -Force | Out-Null

Write-Status "创建构建目录" "Success"

# 复制核心文件
Write-Status "复制 nanobot 源代码..."
Copy-Item -Path "nanobot" -Destination "$TEMP_DIR\nanobot" -Recurse -Force
Write-Status "源代码复制完成" "Success"

# 复制部署脚本
Write-Status "复制部署脚本..."
Copy-Item -Path "deploy_agent_node.ps1" -Destination "$TEMP_DIR\" -Force
Copy-Item -Path "AGENT_NODE_DEPLOYMENT.md" -Destination "$TEMP_DIR\" -Force
Write-Status "部署脚本复制完成" "Success"

# 复制项目配置
Write-Status "复制项目配置..."
Copy-Item -Path "pyproject.toml" -Destination "$TEMP_DIR\" -Force
Copy-Item -Path "README.md" -Destination "$TEMP_DIR\" -Force
if (Test-Path "LICENSE") {
    Copy-Item -Path "LICENSE" -Destination "$TEMP_DIR\" -Force
}
Write-Status "项目配置复制完成" "Success"

# 生成 requirements.txt
Write-Status "生成依赖列表..."
$requirementsContent = @"
typer>=0.20.0,<1.0.0
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
"@

Set-Content -Path "$TEMP_DIR\requirements.txt" -Value $requirementsContent
Write-Status "依赖列表生成完成" "Success"

# 创建安装脚本
Write-Status "创建安装脚本..."
$installScript = @'
# Nanobot Agent Node 安装脚本
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
'@

Set-Content -Path "$TEMP_DIR\install.ps1" -Value $installScript
Write-Status "安装脚本创建完成" "Success"

# 创建快速启动脚本
Write-Status "创建快速启动脚本..."
$startScript = @'
@echo off
REM Nanobot Agent Node 快速启动脚本

setlocal enabledelayedexpansion

set VENV_PATH=%USERPROFILE%\nanobot\.venv
set ACTIVATE_SCRIPT=!VENV_PATH!\Scripts\activate.bat

if not exist !ACTIVATE_SCRIPT! (
    echo [错误] 虚拟环境不存在
    echo 请先运行 install.ps1 进行安装
    echo.
    pause
    exit /b 1
)

echo [*] 激活虚拟环境...
call !ACTIVATE_SCRIPT!

echo [*] 启动 Nanobot Gateway...
echo.
nanobot gateway

pause
'@

Set-Content -Path "$TEMP_DIR\start.bat" -Value $startScript
Write-Status "快速启动脚本创建完成" "Success"

# 创建 README
Write-Status "创建安装说明..."
$readmeContent = @"
# Nanobot Agent Node Windows 安装包

版本: $PACKAGE_VERSION

## 快速开始

### 第一步：安装 Python

1. 下载 Python 3.11+: https://www.python.org/downloads/
2. 运行安装程序
3. **重要**：勾选 "Add Python to PATH"
4. 完成安装

验证安装：打开 cmd 或 PowerShell，运行：
\`\`\`
python --version
\`\`\`

### 第二步：运行安装脚本

**方式 A：使用 PowerShell（推荐）**

1. 右键点击 \`install.ps1\`
2. 选择 "使用 PowerShell 运行"
3. 如果提示权限错误，运行：
   \`\`\`powershell
   Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope CurrentUser
   \`\`\`
   然后重新运行 \`install.ps1\`

**方式 B：手动安装**

1. 打开 PowerShell
2. 进入解压目录
3. 运行：
   \`\`\`powershell
   powershell -ExecutionPolicy Bypass -File install.ps1
   \`\`\`

### 第三步：配置

编辑 \`%USERPROFILE%\.nanobot\config.json\`：

\`\`\`json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    }
  },
  "agents": {
    "defaults": {
      "model": "anthropic/claude-opus-4-5"
    }
  }
}
\`\`\`

获取 API Key：
- OpenRouter: https://openrouter.ai/keys
- Anthropic: https://console.anthropic.com
- OpenAI: https://platform.openai.com

### 第四步：启动

**方式 A：双击启动**
- 双击 \`start.bat\`

**方式 B：手动启动**
\`\`\`powershell
\$venv = "\$env:USERPROFILE\nanobot\.venv\Scripts\Activate.ps1"
& \$venv
nanobot gateway
\`\`\`

### 第五步：注册到 Control Plane（可选）

如果你有 Control Plane 中控服务器：

1. 从 Control Plane 管理界面获取注册令牌
2. 在 PowerShell 中运行：
   \`\`\`powershell
   \$venv = "\$env:USERPROFILE\nanobot\.venv\Scripts\Activate.ps1"
   & \$venv
   nanobot register --token token_xxx --server http://cp-host:8080
   \`\`\`

## 文件说明

| 文件 | 说明 |
|------|------|
| \`install.ps1\` | 自动安装脚本（推荐使用） |
| \`start.bat\` | 快速启动脚本 |
| \`nanobot/\` | nanobot 源代码 |
| \`requirements.txt\` | Python 依赖列表 |
| \`AGENT_NODE_DEPLOYMENT.md\` | 详细部署指南 |
| \`INSTALL.md\` | 本文件 |

## 故障排查

### 问题 1：无法运行 PowerShell 脚本

**错误信息**：
\`\`\`
cannot be loaded because running scripts is disabled on this system
\`\`\`

**解决方案**：
\`\`\`powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope CurrentUser
\`\`\`

### 问题 2：Python 未找到

**错误信息**：
\`\`\`
'python' is not recognized as an internal or external command
\`\`\`

**解决方案**：
1. 确保 Python 已安装
2. 重启 PowerShell 或 cmd
3. 检查 Python 是否添加到 PATH：
   \`\`\`powershell
   python --version
   \`\`\`

### 问题 3：依赖安装失败

**错误信息**：
\`\`\`
ERROR: Could not find a version that satisfies the requirement
\`\`\`

**解决方案**：
1. 检查网络连接
2. 尝试手动安装：
   \`\`\`powershell
   \$venv = "\$env:USERPROFILE\nanobot\.venv\Scripts\Activate.ps1"
   & \$venv
   pip install --upgrade pip
   pip install -r requirements.txt
   \`\`\`

### 问题 4：启动时出错

**查看日志**：
\`\`\`powershell
Get-Content \$env:USERPROFILE\.nanobot\logs\nanobot.log -Tail 100
\`\`\`

## 常见问题

**Q: 如何更新 nanobot？**

A: 在虚拟环境中运行：
\`\`\`powershell
pip install --upgrade nanobot-ai
\`\`\`

**Q: 如何卸载？**

A: 删除以下目录：
\`\`\`powershell
Remove-Item -Recurse \$env:USERPROFILE\.nanobot
Remove-Item -Recurse \$env:USERPROFILE\nanobot
\`\`\`

**Q: 如何开机自启？**

A: 创建 Windows 计划任务：
\`\`\`powershell
\$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File C:\path\to\start.bat"
\$trigger = New-ScheduledTaskTrigger -AtStartup
Register-ScheduledTask -TaskName "NanobotAgentNode" -Action \$action -Trigger \$trigger -Force
\`\`\`

## 支持

- 文档：https://github.com/HKUDS/nanobot
- 问题反馈：https://github.com/HKUDS/nanobot/issues
- 讨论：https://github.com/HKUDS/nanobot/discussions

---

祝你使用愉快！🚀
"@

Set-Content -Path "$TEMP_DIR\INSTALL.md" -Value $readmeContent
Write-Status "安装说明创建完成" "Success"

# 创建压缩包
Write-Status "创建压缩包..."

try {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory($TEMP_DIR, $ZIP_FILE)
    Write-Status "压缩包创建成功" "Success"
} catch {
    Write-Status "压缩包创建失败: $_" "Error"
    exit 1
}

# 获取文件大小
$fileSize = (Get-Item $ZIP_FILE).Length / 1MB
$fileCount = (Get-ChildItem -Path $TEMP_DIR -Recurse -File).Count

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                    打包完成！                              ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

Write-Status "包名: $PACKAGE_NAME-$PACKAGE_VERSION.zip" "Info"
Write-Status "位置: $ZIP_FILE" "Info"
Write-Status "大小: $([Math]::Round($fileSize, 2)) MB" "Info"
Write-Status "文件数: $fileCount" "Info"

Write-Host ""
Write-Host "下一步:" -ForegroundColor Cyan
Write-Host "  1. 将压缩包复制到目标 Windows 电脑"
Write-Host "  2. 解压缩"
Write-Host "  3. 运行 install.ps1"
Write-Host ""
