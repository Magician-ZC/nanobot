# Nanobot Windows Agent Node 快速部署脚本
# 使用方法: powershell -ExecutionPolicy Bypass -File deploy_windows.ps1 -ControlPlaneUrl "http://cp-host:8080" -RegisterToken "token_xxx"

param(
    [string]$ControlPlaneUrl = "",
    [string]$RegisterToken = "",
    [string]$InstallPath = "$env:USERPROFILE\nanobot",
    [string]$PythonVersion = "3.11"
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

function Test-Python {
    try {
        $version = python --version 2>&1
        Write-Status "检测到 Python: $version" "Success"
        return $true
    }
    catch {
        return $false
    }
}

function Install-Python {
    Write-Status "未检测到 Python，开始下载安装..."

    $pythonUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    $installerPath = "$env:TEMP\python-installer.exe"

    Write-Status "下载 Python 3.11..."
    try {
        Invoke-WebRequest -Uri $pythonUrl -OutFile $installerPath -UseBasicParsing
    }
    catch {
        Write-Status "下载失败，请手动从 https://www.python.org/downloads/ 安装 Python 3.11+" "Error"
        exit 1
    }

    Write-Status "运行 Python 安装程序..."
    & $installerPath /quiet InstallAllUsers=1 PrependPath=1 Include_test=0

    if ($LASTEXITCODE -ne 0) {
        Write-Status "Python 安装失败" "Error"
        exit 1
    }

    Write-Status "Python 安装完成" "Success"
    Remove-Item $installerPath -Force

    # 刷新环境变量
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}

function Create-VirtualEnv {
    param([string]$VenvPath)

    Write-Status "创建虚拟环境: $VenvPath"
    python -m venv $VenvPath

    if ($LASTEXITCODE -ne 0) {
        Write-Status "虚拟环境创建失败" "Error"
        exit 1
    }

    Write-Status "虚拟环境创建成功" "Success"
}

function Install-Nanobot {
    param([string]$VenvPath)

    $activateScript = "$VenvPath\Scripts\Activate.ps1"

    Write-Status "激活虚拟环境..."
    & $activateScript

    Write-Status "升级 pip..."
    python -m pip install --upgrade pip setuptools wheel

    Write-Status "安装 nanobot-ai..."
    pip install nanobot-ai

    if ($LASTEXITCODE -ne 0) {
        Write-Status "nanobot 安装失败" "Error"
        exit 1
    }

    Write-Status "nanobot 安装成功" "Success"
}

function Initialize-Nanobot {
    param([string]$VenvPath)

    $activateScript = "$VenvPath\Scripts\Activate.ps1"

    Write-Status "初始化 nanobot..."
    & $activateScript
    nanobot onboard

    Write-Status "nanobot 初始化完成" "Success"
}

function Configure-ManagedMode {
    param(
        [string]$ControlPlaneUrl,
        [string]$RegisterToken
    )

    if (-not $ControlPlaneUrl -or -not $RegisterToken) {
        Write-Status "跳过受管模式配置（未提供 ControlPlaneUrl 或 RegisterToken）" "Warning"
        return
    }

    $configPath = "$env:USERPROFILE\.nanobot\config.json"

    if (-not (Test-Path $configPath)) {
        Write-Status "配置文件不存在: $configPath" "Error"
        exit 1
    }

    Write-Status "配置受管模式..."

    $config = Get-Content $configPath | ConvertFrom-Json

    # 添加 controlPlane 配置
    if (-not $config.controlPlane) {
        $config | Add-Member -NotePropertyName "controlPlane" -NotePropertyValue @{}
    }

    $config.controlPlane.url = $ControlPlaneUrl
    $config.controlPlane.registerToken = $RegisterToken

    $config | ConvertTo-Json -Depth 10 | Set-Content $configPath

    Write-Status "受管模式配置完成" "Success"
}

function Create-StartupScript {
    param([string]$VenvPath)

    $startupScript = "$InstallPath\start-gateway.ps1"

    $scriptContent = @"
# Nanobot Gateway 启动脚本
`$venvPath = "$VenvPath"
`$activateScript = "`$venvPath\Scripts\Activate.ps1"

Write-Host "启动 Nanobot Gateway..." -ForegroundColor Cyan
& `$activateScript
nanobot gateway
"@

    Set-Content -Path $startupScript -Value $scriptContent
    Write-Status "启动脚本已创建: $startupScript" "Success"
}

function Create-ScheduledTask {
    param([string]$VenvPath)

    $taskName = "NanobotGateway"
    $startupScript = "$InstallPath\start-gateway.ps1"

    Write-Status "创建计划任务: $taskName"

    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$startupScript`""
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force -AsJob | Out-Null

    Write-Status "计划任务已创建，将在系统启动时自动运行" "Success"
}

# ============ 主流程 ============

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     Nanobot Windows Agent Node 快速部署脚本               ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

Write-Status "安装路径: $InstallPath"
Write-Status "Control Plane URL: $(if ($ControlPlaneUrl) { $ControlPlaneUrl } else { '(独立模式)' })"

# 检查 Python
if (-not (Test-Python)) {
    Write-Status "Python 未安装" "Warning"
    Install-Python
}

# 创建安装目录
if (-not (Test-Path $InstallPath)) {
    New-Item -ItemType Directory -Path $InstallPath -Force | Out-Null
    Write-Status "创建安装目录: $InstallPath" "Success"
}

$venvPath = "$InstallPath\.venv"

# 创建虚拟环境
if (-not (Test-Path $venvPath)) {
    Create-VirtualEnv $venvPath
}
else {
    Write-Status "虚拟环境已存在" "Info"
}

# 安装 nanobot
Install-Nanobot $venvPath

# 初始化 nanobot
Initialize-Nanobot $venvPath

# 配置受管模式
if ($ControlPlaneUrl -and $RegisterToken) {
    Configure-ManagedMode $ControlPlaneUrl $RegisterToken
}

# 创建启动脚本
Create-StartupScript $venvPath

# 创建计划任务
Write-Status "是否创建开机自启任务？(Y/N)" "Warning"
$response = Read-Host
if ($response -eq "Y" -or $response -eq "y") {
    Create-ScheduledTask $venvPath
}

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                    部署完成！                              ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

Write-Status "后续步骤:" "Info"
Write-Host "  1. 编辑配置文件: $env:USERPROFILE\.nanobot\config.json"
Write-Host "  2. 添加 LLM Provider API Key"
Write-Host "  3. 运行启动脚本: $InstallPath\start-gateway.ps1"
Write-Host ""
Write-Status "查看日志: Get-Content $env:USERPROFILE\.nanobot\logs\nanobot.log -Tail 50 -Wait" "Info"
Write-Host ""
