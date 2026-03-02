# Nanobot Agent Node Windows 快速部署脚本
# 用途：将 nanobot 打包安装到其他 Windows 电脑，启动时自动注册到 Control Plane
# 使用：powershell -ExecutionPolicy Bypass -File deploy_agent_node.ps1 -ControlPlaneUrl "http://cp-host:8080" -RegisterToken "token_xxx"

param(
    [Parameter(Mandatory=$true)]
    [string]$ControlPlaneUrl,

    [Parameter(Mandatory=$true)]
    [string]$RegisterToken,

    [string]$InstallPath = "$env:USERPROFILE\nanobot",
    [string]$NodeName = $env:COMPUTERNAME
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
    Write-Status "未检测到 Python，开始下载安装..." "Warning"

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
    python -m pip install --upgrade pip setuptools wheel 2>&1 | Out-Null

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

function Create-StartupScript {
    param(
        [string]$VenvPath,
        [string]$ControlPlaneUrl,
        [string]$RegisterToken,
        [string]$NodeName
    )

    $startupScript = "$InstallPath\start-gateway.ps1"

    $scriptContent = @"
# Nanobot Agent Node 启动脚本 - 自动注册到 Control Plane
`$venvPath = "$VenvPath"
`$activateScript = "`$venvPath\Scripts\Activate.ps1"

# 设置环境变量用于自动注册
`$env:NANOBOT_CONTROL_PLANE_URL = "$ControlPlaneUrl"
`$env:NANOBOT_REGISTER_TOKEN = "$RegisterToken"

Write-Host "启动 Nanobot Agent Node..." -ForegroundColor Cyan
Write-Host "Control Plane: $ControlPlaneUrl" -ForegroundColor Cyan
Write-Host "Node Name: $NodeName" -ForegroundColor Cyan
Write-Host ""

& `$activateScript
nanobot gateway
"@

    Set-Content -Path $startupScript -Value $scriptContent
    Write-Status "启动脚本已创建: $startupScript" "Success"
}

function Create-ScheduledTask {
    param([string]$VenvPath)

    $taskName = "NanobotAgentNode"
    $startupScript = "$InstallPath\start-gateway.ps1"

    Write-Status "创建计划任务: $taskName"

    # 删除已存在的任务
    $existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }

    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$startupScript`""
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force -AsJob | Out-Null

    Write-Status "计划任务已创建，将在系统启动时自动运行" "Success"
}

function Create-ConfigTemplate {
    param([string]$NodeName)

    $configPath = "$env:USERPROFILE\.nanobot\config.json"

    if (Test-Path $configPath) {
        Write-Status "配置文件已存在，跳过创建" "Info"
        return
    }

    Write-Status "创建配置文件模板..."

    $configTemplate = @{
        agents = @{
            defaults = @{
                model = "anthropic/claude-opus-4-5"
                temperature = 0.7
                max_tokens = 4096
                max_tool_iterations = 10
            }
        }
        providers = @{
            openrouter = @{
                apiKey = ""
            }
        }
        channels = @{
            telegram = @{
                enabled = $false
                token = ""
                allowFrom = @()
            }
        }
        tools = @{
            restrictToWorkspace = $true
            exec = @{
                enabled = $true
            }
        }
    } | ConvertTo-Json -Depth 10

    Set-Content -Path $configPath -Value $configTemplate
    Write-Status "配置文件已创建: $configPath" "Success"
    Write-Status "请编辑配置文件，添加 LLM Provider API Key" "Warning"
}

# ============ 主流程 ============

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     Nanobot Agent Node Windows 部署脚本                   ║" -ForegroundColor Cyan
Write-Host "║     (自动注册到 Control Plane)                            ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

Write-Status "部署配置:"
Write-Host "  安装路径: $InstallPath"
Write-Host "  Control Plane: $ControlPlaneUrl"
Write-Host "  注册令牌: $RegisterToken"
Write-Host "  节点名称: $NodeName"
Write-Host ""

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

# 创建配置文件模板
Create-ConfigTemplate $NodeName

# 创建启动脚本（包含环境变量）
Create-StartupScript $venvPath $ControlPlaneUrl $RegisterToken $NodeName

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
Write-Host "     - 添加 LLM Provider API Key（如 OpenRouter）"
Write-Host "     - 配置通道（Telegram、Discord 等）"
Write-Host ""
Write-Host "  2. 启动 Agent Node:"
Write-Host "     - 手动启动: $InstallPath\start-gateway.ps1"
Write-Host "     - 或等待系统重启自动启动"
Write-Host ""
Write-Host "  3. 验证注册:"
Write-Host "     - 访问 Control Plane: $ControlPlaneUrl"
Write-Host "     - 在节点列表中查看此节点状态"
Write-Host ""
Write-Status "查看日志: Get-Content $env:USERPROFILE\.nanobot\logs\nanobot.log -Tail 50 -Wait" "Info"
Write-Host ""
