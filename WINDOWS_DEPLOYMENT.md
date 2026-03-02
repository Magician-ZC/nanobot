# Nanobot Windows 批量部署指南

## 快速开始（单机部署）

### 方式一：自动化部署（推荐）

**独立模式**（本地运行，不连接 Control Plane）：
```powershell
powershell -ExecutionPolicy Bypass -File deploy_windows.ps1
```

**受管模式**（连接到 Control Plane）：
```powershell
powershell -ExecutionPolicy Bypass -File deploy_windows.ps1 `
  -ControlPlaneUrl "http://cp-host:8080" `
  -RegisterToken "token_xxx"
```

**自定义安装路径**：
```powershell
powershell -ExecutionPolicy Bypass -File deploy_windows.ps1 `
  -InstallPath "D:\nanobot" `
  -ControlPlaneUrl "http://cp-host:8080" `
  -RegisterToken "token_xxx"
```

### 方式二：手动部署

如果自动脚本失败，按以下步骤手动部署：

#### 1. 安装 Python 3.11+
- 下载：https://www.python.org/downloads/
- 安装时勾选 "Add Python to PATH"
- 验证：`python --version`

#### 2. 创建虚拟环境
```powershell
python -m venv C:\nanobot\.venv
C:\nanobot\.venv\Scripts\Activate.ps1
```

#### 3. 安装 nanobot
```powershell
pip install --upgrade pip
pip install nanobot-ai
```

#### 4. 初始化
```powershell
nanobot onboard
```

#### 5. 配置
编辑 `%USERPROFILE%\.nanobot\config.json`：
```json
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
```

#### 6. 启动
```powershell
nanobot gateway
```

---

## 批量部署到多台 Windows 电脑

### 场景：通过 Control Plane 统一管理多个 Agent 节点

#### 前置条件
1. Control Plane 已部署并运行（参考 `control_plane/README.md`）
2. 已在 Control Plane 生成注册令牌

#### 步骤一：准备部署包

在 Control Plane 管理界面或通过 API 生成部署脚本：

```bash
# 从 Control Plane 获取部署脚本
curl -X GET "http://cp-host:8080/api/deploy/script?type=windows&token=token_xxx" \
  -H "Authorization: Bearer <admin_jwt>" \
  > deploy_nanobot.ps1
```

或在管理界面 `/deploy` 页面下载。

#### 步骤二：分发到目标电脑

**方式 A：USB 或网络共享**
```powershell
# 在源电脑上
Copy-Item deploy_windows.ps1 \\target-pc\c$\temp\

# 在目标电脑上
powershell -ExecutionPolicy Bypass -File C:\temp\deploy_windows.ps1 `
  -ControlPlaneUrl "http://cp-host:8080" `
  -RegisterToken "token_xxx"
```

**方式 B：远程执行（需要 WinRM 启用）**
```powershell
# 在管理电脑上
$computers = @("pc1", "pc2", "pc3")
$scriptPath = "C:\deploy_windows.ps1"
$cpUrl = "http://cp-host:8080"
$token = "token_xxx"

foreach ($computer in $computers) {
    Write-Host "部署到 $computer..."
    Invoke-Command -ComputerName $computer -ScriptBlock {
        param($script, $url, $tok)
        powershell -ExecutionPolicy Bypass -File $script `
          -ControlPlaneUrl $url `
          -RegisterToken $tok
    } -ArgumentList $scriptPath, $cpUrl, $token
}
```

**方式 C：Group Policy（企业环境）**

1. 将 `deploy_windows.ps1` 放到 SYSVOL 共享
2. 创建 GPO 启动脚本，执行：
```powershell
powershell -ExecutionPolicy Bypass -File "\\domain\sysvol\deploy_windows.ps1" `
  -ControlPlaneUrl "http://cp-host:8080" `
  -RegisterToken "token_xxx"
```

#### 步骤三：验证部署

在 Control Plane 管理界面查看节点状态：
- 访问 `http://cp-host:8080/nodes`
- 确认所有节点显示为 "online"

或通过 API：
```bash
curl -X GET "http://cp-host:8080/api/nodes" \
  -H "Authorization: Bearer <admin_jwt>"
```

---

## 配置管理

### 独立模式配置

编辑 `%USERPROFILE%\.nanobot\config.json`：

```json
{
  "agents": {
    "defaults": {
      "model": "anthropic/claude-opus-4-5",
      "temperature": 0.7,
      "max_tokens": 4096
    }
  },
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"]
    }
  },
  "tools": {
    "restrictToWorkspace": true
  }
}
```

### 受管模式配置

受管模式下，配置由 Control Plane 下发，本地配置会被覆盖。

在 Control Plane 管理界面为节点配置：
1. 选择节点
2. 编辑配置（agents、channels、providers）
3. 设置策略（allowed_skills、allowed_mcp_servers）
4. 保存并重启节点

---

## 启动和管理

### 手动启动
```powershell
# 激活虚拟环境
C:\nanobot\.venv\Scripts\Activate.ps1

# 启动 gateway
nanobot gateway
```

### 开机自启（计划任务）

部署脚本会自动创建计划任务。如需手动创建：

```powershell
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-ExecutionPolicy Bypass -File C:\nanobot\start-gateway.ps1"
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "NanobotGateway" -Action $action -Trigger $trigger -Settings $settings -Force
```

### 查看日志
```powershell
# 实时查看日志
Get-Content $env:USERPROFILE\.nanobot\logs\nanobot.log -Tail 50 -Wait

# 或在 Control Plane 管理界面查看
# http://cp-host:8080/nodes/<node_id>/logs
```

### 停止服务
```powershell
# 停止计划任务
Stop-ScheduledTask -TaskName "NanobotGateway"

# 或直接关闭 PowerShell 窗口（Ctrl+C）
```

---

## 故障排查

### Python 安装失败
```powershell
# 手动下载并安装
# https://www.python.org/downloads/
# 安装时勾选 "Add Python to PATH"

# 验证
python --version
```

### nanobot 安装失败
```powershell
# 检查 pip
python -m pip --version

# 升级 pip
python -m pip install --upgrade pip

# 重试安装
pip install nanobot-ai
```

### 无法连接 Control Plane
```powershell
# 检查网络连通性
Test-NetConnection -ComputerName cp-host -Port 8080

# 检查配置
Get-Content $env:USERPROFILE\.nanobot\config.json | ConvertFrom-Json | Select-Object controlPlane

# 查看日志
Get-Content $env:USERPROFILE\.nanobot\logs\nanobot.log -Tail 100
```

### 虚拟环境激活失败
```powershell
# 检查执行策略
Get-ExecutionPolicy

# 临时允许
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process

# 或使用完整路径
C:\nanobot\.venv\Scripts\python.exe -m nanobot.cli.commands gateway
```

---

## 高级配置

### 自定义 LLM Provider

在 Control Plane 中配置 LLM Key 池，节点会自动获取分配的 Key。

或在本地配置（独立模式）：
```json
{
  "providers": {
    "custom": {
      "apiKey": "your-key",
      "apiBase": "https://api.your-provider.com/v1"
    }
  },
  "agents": {
    "defaults": {
      "model": "your-model-name"
    }
  }
}
```

### MCP 工具扩展

在配置中添加 MCP Server：
```json
{
  "tools": {
    "mcpServers": {
      "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:\\workspace"]
      }
    }
  }
}
```

### 安全配置

```json
{
  "tools": {
    "restrictToWorkspace": true,
    "exec": {
      "enabled": true
    }
  },
  "channels": {
    "telegram": {
      "allowFrom": ["YOUR_USER_ID"]
    }
  }
}
```

---

## 常见问题

**Q: 如何更新 nanobot？**
```powershell
pip install --upgrade nanobot-ai
nanobot gateway  # 重启
```

**Q: 如何卸载？**
```powershell
pip uninstall nanobot-ai
Remove-Item -Recurse $env:USERPROFILE\.nanobot
```

**Q: 支持 WhatsApp 吗？**

WhatsApp 需要 Node.js ≥18。在 Windows 上：
```powershell
# 安装 Node.js: https://nodejs.org/
# 然后
nanobot channels login  # 扫码绑定
```

**Q: 如何在多个 Windows 电脑间同步配置？**

使用 Control Plane 受管模式，所有配置由中心下发，自动同步。

---

## 支持

- 文档：https://github.com/HKUDS/nanobot
- 问题反馈：https://github.com/HKUDS/nanobot/issues
- 讨论：https://github.com/HKUDS/nanobot/discussions
