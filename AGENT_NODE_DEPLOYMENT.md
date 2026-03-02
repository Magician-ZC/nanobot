# Nanobot Control Plane + Agent Nodes 部署架构

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                   Control Plane (中控)                      │
│              运行在主服务器 (Linux/Mac/Windows)              │
│  - FastAPI 后端 (管理节点、配置、LLM Key、审计日志)         │
│  - Vue.js 前端 (Web 管理界面)                               │
│  - SQLite 数据库 (节点信息、配置、日志)                     │
└─────────────────────────────────────────────────────────────┘
                            ↑
                    WebSocket 长连接
                            ↓
    ┌───────────────────────┼───────────────────────┐
    ↓                       ↓                       ↓
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│ Agent Node  │      │ Agent Node  │      │ Agent Node  │
│ (Windows 1) │      │ (Windows 2) │      │ (Windows N) │
│             │      │             │      │             │
│ - nanobot   │      │ - nanobot   │      │ - nanobot   │
│ - 自动注册  │      │ - 自动注册  │      │ - 自动注册  │
│ - 接收配置  │      │ - 接收配置  │      │ - 接收配置  │
└─────────────┘      └─────────────┘      └─────────────┘
```

## 部署流程

### 第一步：部署 Control Plane（中控）

在主服务器上部署 Control Plane：

```bash
# 1. 克隆项目
git clone https://github.com/HKUDS/nanobot.git
cd nanobot

# 2. 安装 Control Plane 依赖
pip install -e ./control_plane

# 3. 启动 Control Plane
python control_plane/run.py --port 8080

# 首次启动会输出 admin 密码，请记录
```

访问 `http://localhost:8080` 进入管理界面。

### 第二步：在 Control Plane 生成注册令牌

1. 登录管理界面
2. 进入 **节点管理** → **生成注册令牌**
3. 复制令牌（格式：`token_xxx`）

或通过 API：
```bash
curl -X POST http://localhost:8080/api/nodes/registration-tokens \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "admin"}'
```

### 第三步：打包 Agent Node 部署脚本

在主服务器上准备部署包：

```bash
# 复制部署脚本到一个目录
mkdir -p ~/nanobot-deployment
cp deploy_agent_node.ps1 ~/nanobot-deployment/
cp AGENT_NODE_DEPLOYMENT.md ~/nanobot-deployment/
```

### 第四步：分发到目标 Windows 电脑

**方式 A：USB 或网络共享**
```powershell
# 在目标电脑上
powershell -ExecutionPolicy Bypass -File deploy_agent_node.ps1 `
  -ControlPlaneUrl "http://cp-host:8080" `
  -RegisterToken "token_xxx"
```

**方式 B：远程执行（需要 WinRM）**
```powershell
# 在管理电脑上
$computers = @("pc1", "pc2", "pc3")
$cpUrl = "http://cp-host:8080"
$token = "token_xxx"

foreach ($computer in $computers) {
    Write-Host "部署到 $computer..."
    Invoke-Command -ComputerName $computer -ScriptBlock {
        param($url, $tok)
        powershell -ExecutionPolicy Bypass -File C:\temp\deploy_agent_node.ps1 `
          -ControlPlaneUrl $url `
          -RegisterToken $tok
    } -ArgumentList $cpUrl, $token
}
```

### 第五步：验证节点注册

1. 在 Control Plane 管理界面查看节点列表
2. 确认所有节点显示为 "online"
3. 为每个节点配置 LLM Key 和策略

---

## 关键特性

### ✅ 自动注册流程

Agent Node 启动时：
1. 检测环境变量 `NANOBOT_REGISTER_TOKEN` 和 `NANOBOT_CONTROL_PLANE_URL`
2. 自动向 Control Plane 注册
3. 获取 `node_id` 和 `api_key`
4. 保存到本地配置
5. 建立 WebSocket 连接到 Control Plane

### ✅ 配置下发

Control Plane 可以：
- 为每个节点下发不同的配置（agents、channels、providers）
- 管理 LLM API Key 池，按需分配给节点
- 设置策略（allowed_skills、allowed_mcp_servers）
- 实时更新，无需重启节点

### ✅ 开机自启

部署脚本自动创建 Windows 计划任务，确保：
- 系统启动时自动启动 Agent Node
- 自动连接到 Control Plane
- 失败自动重试

### ✅ 集中管理

在 Control Plane 管理界面可以：
- 查看所有节点的在线状态
- 查看节点日志
- 远程配置节点
- 管理 LLM Key 分配
- 审计所有操作

---

## 配置管理

### Control Plane 端

在管理界面为节点配置：

```json
{
  "agents": {
    "defaults": {
      "model": "anthropic/claude-opus-4-5",
      "temperature": 0.7
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN"
    }
  },
  "tools": {
    "restrictToWorkspace": true
  }
}
```

### Agent Node 端

本地配置 `~/.nanobot/config.json` 会被 Control Plane 配置覆盖。

首次启动时需要编辑本地配置添加 LLM Provider（如果 Control Plane 未分配）：

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    }
  }
}
```

---

## 故障排查

### 节点无法注册

```powershell
# 检查网络连通性
Test-NetConnection -ComputerName cp-host -Port 8080

# 查看日志
Get-Content $env:USERPROFILE\.nanobot\logs\nanobot.log -Tail 100
```

### 节点注册后离线

```powershell
# 检查 WebSocket 连接
Get-Content $env:USERPROFILE\.nanobot\logs\nanobot.log | Select-String "WebSocket"

# 重启节点
Stop-ScheduledTask -TaskName "NanobotAgentNode"
Start-ScheduledTask -TaskName "NanobotAgentNode"
```

### Control Plane 无法连接节点

- 检查防火墙设置
- 确认 Control Plane 地址正确
- 查看 Control Plane 日志

---

## 常见问题

**Q: 如何添加新的 Agent Node？**

A: 在 Control Plane 生成新的注册令牌，然后在目标电脑运行部署脚本。

**Q: 如何更新所有节点的配置？**

A: 在 Control Plane 管理界面修改配置，自动下发到所有节点。

**Q: 如何为不同节点分配不同的 LLM Key？**

A: 在 Control Plane 的 LLM Key 管理页面，为每个节点分配不同的 Key。

**Q: 节点可以离线运行吗？**

A: 可以。首次连接成功后，配置会缓存到本地。离线时使用缓存配置继续运行。

**Q: 如何卸载 Agent Node？**

A: 运行卸载脚本或手动删除 `%USERPROFILE%\.nanobot` 目录。

---

## 下一步

1. 部署 Control Plane
2. 生成注册令牌
3. 使用 `deploy_agent_node.ps1` 部署 Agent Node
4. 在 Control Plane 管理界面验证节点
5. 配置 LLM Key 和策略
6. 启动 Agent Node 开始工作
