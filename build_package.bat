@echo off
REM Nanobot Agent Node Windows 打包脚本
REM 用途：将 nanobot 打包成可直接安装的压缩包
REM 运行：build_package.bat

setlocal enabledelayedexpansion

set PACKAGE_NAME=nanobot-agent-node-windows
set PACKAGE_VERSION=0.1.4
set BUILD_DIR=build
set DIST_DIR=dist
set TEMP_DIR=%BUILD_DIR%\%PACKAGE_NAME%-%PACKAGE_VERSION%

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║     Nanobot Agent Node Windows 打包脚本                   ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

REM 清理旧的构建目录
if exist %BUILD_DIR% (
    echo [*] 清理旧的构建目录...
    rmdir /s /q %BUILD_DIR%
)
if exist %DIST_DIR% (
    rmdir /s /q %DIST_DIR%
)

mkdir %BUILD_DIR%
mkdir %DIST_DIR%
mkdir %TEMP_DIR%

echo [✓] 创建构建目录

REM 复制核心文件
echo [*] 复制 nanobot 源代码...
xcopy /E /I /Y nanobot %TEMP_DIR%\nanobot > nul
echo [✓] 源代码复制完成

REM 复制部署脚本
echo [*] 复制部署脚本...
copy deploy_agent_node.ps1 %TEMP_DIR%\ > nul
copy AGENT_NODE_DEPLOYMENT.md %TEMP_DIR%\ > nul
echo [✓] 部署脚本复制完成

REM 复制 pyproject.toml
echo [*] 复制项目配置...
copy pyproject.toml %TEMP_DIR%\ > nul
copy README.md %TEMP_DIR%\ > nul
copy LICENSE %TEMP_DIR%\ > nul
echo [✓] 项目配置复制完成

REM 创建 requirements.txt
echo [*] 生成依赖列表...
python -c "
import re
with open('pyproject.toml', 'r') as f:
    content = f.read()

# 提取 dependencies
match = re.search(r'dependencies = \[(.*?)\]', content, re.DOTALL)
if match:
    deps_str = match.group(1)
    deps = re.findall(r'\"([^\"]+)\"', deps_str)
    with open('%TEMP_DIR%\\requirements.txt', 'w') as out:
        for dep in deps:
            out.write(dep + '\n')
" > nul 2>&1

if exist %TEMP_DIR%\requirements.txt (
    echo [✓] 依赖列表生成完成
) else (
    echo [!] 自动生成失败，使用默认依赖列表
    (
        echo typer^>=0.20.0,^<1.0.0
        echo litellm^>=1.81.5,^<2.0.0
        echo pydantic^>=2.12.0,^<3.0.0
        echo pydantic-settings^>=2.12.0,^<3.0.0
        echo websockets^>=16.0,^<17.0
        echo websocket-client^>=1.9.0,^<2.0.0
        echo httpx^>=0.28.0,^<1.0.0
        echo oauth-cli-kit^>=0.1.3,^<1.0.0
        echo loguru^>=0.7.3,^<1.0.0
        echo readability-lxml^>=0.8.4,^<1.0.0
        echo rich^>=14.0.0,^<15.0.0
        echo croniter^>=6.0.0,^<7.0.0
        echo dingtalk-stream^>=0.24.0,^<1.0.0
        echo python-telegram-bot[socks]^>=22.0,^<23.0
        echo lark-oapi^>=1.5.0,^<2.0.0
        echo socksio^>=1.0.0,^<2.0.0
        echo python-socketio^>=5.16.0,^<6.0.0
        echo msgpack^>=1.1.0,^<2.0.0
        echo slack-sdk^>=3.39.0,^<4.0.0
        echo slackify-markdown^>=0.2.0,^<1.0.0
        echo qq-botpy^>=1.2.0,^<2.0.0
        echo python-socks[asyncio]^>=2.8.0,^<3.0.0
        echo prompt-toolkit^>=3.0.50,^<4.0.0
        echo mcp^>=1.26.0,^<2.0.0
        echo json-repair^>=0.57.0,^<1.0.0
    ) > %TEMP_DIR%\requirements.txt
    echo [✓] 默认依赖列表已创建
)

REM 创建安装脚本
echo [*] 创建安装脚本...
(
    echo # Nanobot Agent Node 安装脚本
    echo # 这个脚本会自动安装 nanobot 并注册到 Control Plane
    echo.
    echo $ErrorActionPreference = "Stop"
    echo.
    echo function Write-Status {
    echo     param([string]$Message, [string]$Type = "Info"^)
    echo     $timestamp = Get-Date -Format "HH:mm:ss"
    echo     switch ($Type^) {
    echo         "Success" { Write-Host "[$timestamp] ✓ $Message" -ForegroundColor Green }
    echo         "Error" { Write-Host "[$timestamp] ✗ $Message" -ForegroundColor Red }
    echo         "Warning" { Write-Host "[$timestamp] ⚠ $Message" -ForegroundColor Yellow }
    echo         default { Write-Host "[$timestamp] ℹ $Message" -ForegroundColor Cyan }
    echo     }
    echo }
    echo.
    echo Write-Host ""
    echo Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    echo Write-Host "║     Nanobot Agent Node 安装程序                           ║" -ForegroundColor Cyan
    echo Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    echo Write-Host ""
    echo.
    echo # 检查 Python
    echo Write-Status "检查 Python..."
    echo try {
    echo     $version = python --version 2^>^&1
    echo     Write-Status "检测到 Python: $version" "Success"
    echo } catch {
    echo     Write-Status "Python 未安装，请先安装 Python 3.11+" "Error"
    echo     Write-Host "下载地址: https://www.python.org/downloads/" -ForegroundColor Yellow
    echo     exit 1
    echo }
    echo.
    echo # 创建虚拟环境
    echo $venvPath = "$env:USERPROFILE\nanobot\.venv"
    echo if (-not (Test-Path $venvPath^)^) {
    echo     Write-Status "创建虚拟环境..."
    echo     python -m venv $venvPath
    echo     if ($LASTEXITCODE -ne 0^) {
    echo         Write-Status "虚拟环境创建失败" "Error"
    echo         exit 1
    echo     }
    echo     Write-Status "虚拟环境创建成功" "Success"
    echo } else {
    echo     Write-Status "虚拟环境已存在" "Info"
    echo }
    echo.
    echo # 激活虚拟环境
    echo $activateScript = "$venvPath\Scripts\Activate.ps1"
    echo Write-Status "激活虚拟环境..."
    echo ^& $activateScript
    echo.
    echo # 升级 pip
    echo Write-Status "升级 pip..."
    echo python -m pip install --upgrade pip setuptools wheel 2^>^&1 ^| Out-Null
    echo.
    echo # 安装依赖
    echo Write-Status "安装依赖包..."
    echo pip install -r requirements.txt
    echo if ($LASTEXITCODE -ne 0^) {
    echo     Write-Status "依赖安装失败" "Error"
    echo     exit 1
    echo }
    echo Write-Status "依赖安装成功" "Success"
    echo.
    echo # 初始化 nanobot
    echo Write-Status "初始化 nanobot..."
    echo nanobot onboard
    echo Write-Status "初始化完成" "Success"
    echo.
    echo Write-Host ""
    echo Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
    echo Write-Host "║                    安装完成！                              ║" -ForegroundColor Green
    echo Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Green
    echo Write-Host ""
    echo.
    echo Write-Status "后续步骤:" "Info"
    echo Write-Host "  1. 编辑配置文件: $env:USERPROFILE\.nanobot\config.json"
    echo Write-Host "     - 添加 LLM Provider API Key"
    echo Write-Host ""
    echo Write-Host "  2. 启动 Agent Node:"
    echo Write-Host "     - 运行: $activateScript"
    echo Write-Host "     - 然后: nanobot gateway"
    echo Write-Host ""
    echo Write-Host "  3. 注册到 Control Plane:"
    echo Write-Host "     - 运行: nanobot register --token token_xxx --server http://cp-host:8080"
    echo Write-Host ""
) > %TEMP_DIR%\install.ps1

echo [✓] 安装脚本创建完成

REM 创建快速启动脚本
echo [*] 创建快速启动脚本...
(
    echo @echo off
    echo REM Nanobot Agent Node 快速启动脚本
    echo.
    echo set VENV_PATH=%USERPROFILE%\nanobot\.venv
    echo set ACTIVATE_SCRIPT=!VENV_PATH!\Scripts\activate.bat
    echo.
    echo if not exist !ACTIVATE_SCRIPT! (
    echo     echo [错误] 虚拟环境不存在，请先运行 install.ps1
    echo     pause
    echo     exit /b 1
    echo )
    echo.
    echo echo [*] 激活虚拟环境...
    echo call !ACTIVATE_SCRIPT!
    echo.
    echo echo [*] 启动 Nanobot Gateway...
    echo nanobot gateway
    echo.
    echo pause
) > %TEMP_DIR%\start.bat

echo [✓] 快速启动脚本创建完成

REM 创建 README
echo [*] 创建安装说明...
(
    echo # Nanobot Agent Node Windows 安装包
    echo.
    echo ## 快速开始
    echo.
    echo ### 1. 安装 Python
    echo - 下载 Python 3.11+: https://www.python.org/downloads/
    echo - 安装时勾选 "Add Python to PATH"
    echo - 验证: 打开 cmd，运行 `python --version`
    echo.
    echo ### 2. 运行安装脚本
    echo - 右键点击 `install.ps1`
    echo - 选择 "使用 PowerShell 运行"
    echo - 或在 PowerShell 中运行:
    echo   ```
    echo   powershell -ExecutionPolicy Bypass -File install.ps1
    echo   ```
    echo.
    echo ### 3. 配置
    echo - 编辑 `%%USERPROFILE%%\.nanobot\config.json`
    echo - 添加 LLM Provider API Key（如 OpenRouter）
    echo.
    echo ### 4. 启动
    echo - 双击 `start.bat` 启动 Agent Node
    echo - 或在 PowerShell 中运行:
    echo   ```
    echo   $venv = "$env:USERPROFILE\nanobot\.venv\Scripts\Activate.ps1"
    echo   ^& $venv
    echo   nanobot gateway
    echo   ```
    echo.
    echo ### 5. 注册到 Control Plane
    echo - 获取注册令牌（从 Control Plane 管理界面）
    echo - 运行:
    echo   ```
    echo   nanobot register --token token_xxx --server http://cp-host:8080
    echo   ```
    echo.
    echo ## 文件说明
    echo.
    echo - `install.ps1` - 自动安装脚本（推荐）
    echo - `start.bat` - 快速启动脚本
    echo - `nanobot/` - nanobot 源代码
    echo - `requirements.txt` - Python 依赖列表
    echo - `AGENT_NODE_DEPLOYMENT.md` - 详细部署指南
    echo.
    echo ## 故障排查
    echo.
    echo ### 无法运行 PowerShell 脚本
    echo ```powershell
    echo Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope CurrentUser
    echo ```
    echo.
    echo ### Python 未找到
    echo - 确保 Python 已安装并添加到 PATH
    echo - 重启 PowerShell 或 cmd
    echo.
    echo ### 依赖安装失败
    echo - 检查网络连接
    echo - 尝试手动运行: `pip install -r requirements.txt`
    echo.
) > %TEMP_DIR%\INSTALL.md

echo [✓] 安装说明创建完成

REM 计算包大小
for /f %%A in ('dir /s /b %TEMP_DIR% ^| find /c /v ""') do set FILE_COUNT=%%A

echo.
echo [*] 创建压缩包...
cd %BUILD_DIR%

REM 使用 PowerShell 创建 zip 文件
powershell -Command "Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::CreateFromDirectory('%TEMP_DIR%', '..\%DIST_DIR%\%PACKAGE_NAME%-%PACKAGE_VERSION%.zip')"

cd ..

if exist %DIST_DIR%\%PACKAGE_NAME%-%PACKAGE_VERSION%.zip (
    echo [✓] 压缩包创建成功

    REM 获取文件大小
    for /f %%A in ('dir /b %DIST_DIR%\%PACKAGE_NAME%-%PACKAGE_VERSION%.zip') do (
        for /f %%B in ('dir %DIST_DIR%\%PACKAGE_NAME%-%PACKAGE_VERSION%.zip ^| find "%%A"') do (
            set SIZE=%%B
        )
    )

    echo.
    echo ╔════════════════════════════════════════════════════════════╗
    echo ║                    打包完成！                              ║
    echo ╚════════════════════════════════════════════════════════════╝
    echo.
    echo 包名: %PACKAGE_NAME%-%PACKAGE_VERSION%.zip
    echo 位置: %DIST_DIR%\%PACKAGE_NAME%-%PACKAGE_VERSION%.zip
    echo 文件数: !FILE_COUNT!
    echo.
    echo 下一步:
    echo   1. 将压缩包复制到目标 Windows 电脑
    echo   2. 解压缩
    echo   3. 运行 install.ps1
    echo.
) else (
    echo [✗] 压缩包创建失败
    exit /b 1
)

pause
