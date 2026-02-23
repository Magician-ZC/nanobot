# Nanobot 操作手册

## 1. 项目概述

Nanobot 是一个超轻量级个人 AI 助手框架（核心代码约 3,761 行），支持多通道集成和分布式部署。

系统由两个独立组件构成：

| 组件 | 角色 | 技术栈 |
|------|------|--------|
| **Nanobot (Agent Node)** | AI 代理节点，处理消息、调用 LLM、执行工具 | Python + Typer CLI |
| **Control Plane** | 中央管理平面，多节点管理、配置下发、飞书网关 | FastAPI + SQLite + Vue.js |

两种运行模式：
- **独立模式**：单节点本地运行，配置文件在 `~/.nanobot/config.json`
- **受管模式**：多节点通过 Control Plane 统一管理

---

## 2. 环境准备

### 2.1 系统要求

- Python ≥ 3.11
- Node.js ≥ 18（仅 WhatsApp 通道需要）
- pip 或 uv 包管理器

### 2.2 安装

```bash
# 方式一：从源码安装（推荐开发）
git clone https://github.com/HKUDS/nanobot.git
cd nanobot
pip install -e .

# 方式二：PyPI 安装
pip install nanobot-ai

# 方式三：uv 安装
uv tool install nanobot-ai

# 如需 Control Plane，额外安装依赖
pip install nanobot-ai[control-plane]
```

---

## 3. 独立模式操作

### 3.1 初始化

```bash
nanobot onboard
```

此命令会：
- 创建配置文件 `~/.nanobot/config.json`
- 创建工作区 `~/.nanobot/workspace/`（含 AGENTS.md、SOUL.md、USER.md、memory/）

### 3.2 配置 LLM Provider

编辑 `~/.nanobot/config.json`，至少配置一个 Provider 和模型：

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

支持的 Provider：openrouter、anthropic、openai、deepseek、groq、gemini、minimax、dashscope、moonshot、zhipu、vllm、custom 等。

### 3.3 基本使用

```bash
# 单条消息
nanobot agent -m "你好"

# 交互式聊天
nanobot agent

# 查看状态
nanobot status

# 纯文本输出（不渲染 Markdown）
nanobot agent --no-markdown

# 显示运行日志
nanobot agent --logs
```

### 3.4 启动 Gateway（通道服务）

```bash
nanobot gateway
```

Gateway 会启动所有已启用的通道（Telegram、Discord、飞书等），并运行：
- Agent Loop（消息处理循环）
- Channel Manager（通道管理）
- Cron Service（定时任务）
- Heartbeat Service（30 分钟间隔的主动唤醒）

### 3.5 通道配置

在 `config.json` 的 `channels` 段配置各通道：


#### Telegram

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"]
    }
  }
}
```

#### 飞书（本地直连模式）

```json
{
  "channels": {
    "feishu": {
      "enabled": true,
      "appId": "cli_xxx",
      "appSecret": "xxx"
    }
  }
}
```

#### Discord

```json
{
  "channels": {
    "discord": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"]
    }
  }
}
```

#### WhatsApp

需要 Node.js ≥ 18，先扫码登录：

```bash
nanobot channels login    # 扫码绑定
nanobot gateway           # 另一个终端启动 gateway
```

#### 其他通道

Slack、DingTalk、Email、QQ、Mochat 的配置详见 README.md。

### 3.6 通道管理命令

```bash
nanobot channels status   # 查看通道状态
nanobot channels login    # WhatsApp 扫码登录
```

### 3.7 定时任务

```bash
nanobot cron add --name "morning" --message "早安！" --cron "0 9 * * *"
nanobot cron add --name "check" --message "检查状态" --every 3600
nanobot cron list
nanobot cron remove <job_id>
```

### 3.8 MCP 工具扩展

在 `config.json` 中添加 MCP Server：

```json
{
  "tools": {
    "mcpServers": {
      "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"]
      },
      "remote-server": {
        "url": "https://mcp.example.com/sse"
      }
    }
  }
}
```

### 3.9 安全配置

```json
{
  "tools": {
    "restrictToWorkspace": true
  },
  "channels": {
    "telegram": {
      "allowFrom": ["YOUR_USER_ID"]
    }
  }
}
```

- `restrictToWorkspace: true`：限制所有工具操作在工作区目录内
- `allowFrom`：通道白名单，空数组 = 允许所有人

---

## 4. Control Plane 操作

### 4.1 启动 Control Plane

Control Plane 已拆分为独立项目，位于 `control_plane_standalone/` 目录。

```bash
# 进入独立项目目录
cd control_plane_standalone

# 方式一：直接运行
python run.py
python run.py --port 9090 --db /path/to/cp.db

# 方式二：Docker
docker compose up -d
```

首次启动会：
1. 初始化 SQLite 数据库（默认 `data/control_plane.db`）
2. 自动创建 admin 用户并在控制台输出密码（仅首次可见，请立即记录）
3. 启动飞书网关服务和消息路由器
4. 挂载 Vue.js 前端（如已构建）

### 4.2 管理界面

访问 `http://<host>:<port>/` 进入 Web 管理界面，包含以下页面：

| 页面 | 路径 | 功能 |
|------|------|------|
| 登录 | `/login` | 用户认证 |
| 仪表盘 | `/` | 节点概览、状态监控 |
| 节点详情 | `/nodes/:id` | 单节点配置、策略、日志 |
| 用户管理 | `/users` | 创建/编辑用户 |
| 任务管理 | `/tasks` | 分布式任务锁 |
| Token 用量 | `/token-usage` | LLM 调用统计 |
| 飞书网关 | `/feishu-gateway` | 飞书共享网关配置 |

### 4.3 API 概览

所有 API 以 `/api` 为前缀：

| 模块 | 路径前缀 | 功能 |
|------|---------|------|
| 认证 | `/api/auth/` | 登录、用户 CRUD |
| 节点 | `/api/nodes/` | 注册、心跳、配置、策略 |
| LLM Key | `/api/llm-keys/` | Key 池管理、分配 |
| 策略 | `/api/policies/` | 资源策略管理 |
| 部署 | `/api/deploy/` | 一键部署脚本生成 |
| 飞书网关 | `/api/feishu-gateway/` | 网关配置、绑定、消息 |
| 审计 | `/api/audit/` | 审计日志查询 |
| 日志 | `/api/logs/` | 节点日志查询 |
| 任务 | `/api/tasks/` | 分布式任务锁 |
| Skill 仓库 | `/api/skills/` | Skill 注册、上传、下载 |

### 4.4 节点管理流程

#### 步骤一：生成注册令牌

在 Control Plane 管理界面或通过 API 生成一次性注册令牌：

```bash
# API 方式
curl -X POST http://cp-host:8080/api/nodes/registration-tokens \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "<user_id>"}'
```

#### 步骤二：部署 Agent Node

**Docker 一键部署：**

```bash
docker run -d --name nanobot \
  --restart unless-stopped \
  -v ~/.nanobot:/root/.nanobot \
  -e NANOBOT_REGISTER_TOKEN=<token_id> \
  -e NANOBOT_CONTROL_PLANE_URL=http://cp-host:8080 \
  nanobot-ai gateway
```

**pip 手动部署：**

```bash
pip install nanobot-ai
nanobot onboard
# 编辑 ~/.nanobot/config.json，添加 controlPlane 段：
# {
#   "controlPlane": {
#     "url": "http://cp-host:8080",
#     "apiKey": "<node_api_key>",
#     "nodeId": "<node_id>"
#   }
# }
nanobot gateway
```

也可通过管理界面的部署页面自动生成部署脚本。

#### 步骤三：验证节点状态

节点启动后会：
1. 自动注册（Docker 模式）或使用已有凭证连接
2. 拉取远程配置和策略
3. 每 30 秒发送心跳
4. 在管理界面显示为 online

### 4.5 LLM Key 池管理

Control Plane 统一管理 LLM API Key，按需分配给节点：

1. 在管理界面添加 LLM Key（指定 provider、并发限制、用量限制）
2. 为节点分配 Key
3. 节点启动时自动获取分配的 Key，本地 Key 被清空
4. Token 用量自动上报到 Control Plane

### 4.6 策略管理

为每个节点配置资源策略，控制可用的 Skill 和 MCP Server：

```json
{
  "allowed_skills": ["github", "weather"],
  "allowed_mcp_servers": ["filesystem"]
}
```

节点端的 `PolicyEnforcer` 会过滤不在白名单中的资源。

### 4.7 飞书共享网关

适用于多节点共享一个飞书应用的场景：

1. 在管理界面配置飞书应用凭证（App ID、App Secret）
2. Control Plane 维护与飞书的 WebSocket 长连接
3. 飞书用户通过绑定码绑定到特定 Agent Node
4. 消息自动路由：飞书用户 → Control Plane → 对应 Agent Node → 回复

绑定流程：
1. 在管理界面为节点生成绑定码
2. 飞书用户向机器人发送绑定码
3. 绑定成功后，该用户的消息会路由到对应节点

受管模式下，节点的本地飞书通道会自动禁用，避免冲突。

---

## 5. 受管模式详解

### 5.1 受管模式判定

以下任一条件满足即进入受管模式（优先级从高到低）：

1. 存在 `~/.nanobot/.managed` 标记文件
2. 存在 `~/.nanobot/config_cache.enc` 加密缓存
3. `config.json` 中 `controlPlane.url` 非空

### 5.2 受管模式启动流程

```
1. 检测受管模式标记
2. 验证 controlPlane 配置（url、apiKey、nodeId）
3. 连接 Control Plane 拉取远程配置和策略
4. 成功 → 加密缓存到本地；失败 → 尝试使用本地缓存
5. 应用远程配置覆盖本地参数
6. 清空本地所有 Provider 的 API Key
7. 注入 Control Plane 分配的 LLM Key
8. 根据策略过滤 MCP Server
9. 禁用本地飞书通道
10. 启动 GatewayMessageClient（WebSocket 连接 Control Plane）
11. 启动心跳循环（30 秒间隔）
12. 启动 Agent Loop 和通道
```

### 5.3 离线运行

- 首次连接成功后，配置和策略会加密缓存到本地
- 离线时使用本地缓存继续运行
- 无法连接且无缓存时拒绝启动

### 5.4 安全机制

| 层级 | 机制 | 说明 |
|------|------|------|
| 配置管控 | 远程配置覆盖 | 本地 config.json 的 agents/channels/providers/tools 被远程配置替换 |
| LLM Key 管控 | 本地 Key 清空 | 防止节点使用本地 Key 绕过管控 |
| 策略执行 | PolicyEnforcer | 过滤不允许的 Skill 和 MCP Server |
| 审计日志 | 操作记录 | 所有操作和违规上报到 Control Plane |

---

## 6. Docker 部署

### 6.1 Docker Compose

```bash
# 首次初始化
docker compose run --rm nanobot-cli onboard

# 编辑配置
vim ~/.nanobot/config.json

# 启动 gateway
docker compose up -d nanobot-gateway

# 查看日志
docker compose logs -f nanobot-gateway

# 停止
docker compose down
```

### 6.2 单独 Docker

```bash
# 构建镜像
docker build -t nanobot .

# 初始化
docker run -v ~/.nanobot:/root/.nanobot --rm nanobot onboard

# 启动 gateway
docker run -d -v ~/.nanobot:/root/.nanobot -p 18790:18790 nanobot gateway

# 单条消息
docker run -v ~/.nanobot:/root/.nanobot --rm nanobot agent -m "Hello!"
```

---

## 7. 开发指南

### 7.1 开发环境搭建

```bash
git clone https://github.com/HKUDS/nanobot.git
cd nanobot
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,control-plane]"
```

### 7.2 运行测试

```bash
source .venv/bin/activate
pytest tests/
```

### 7.3 前端开发（Control Plane）

```bash
cd control_plane/frontend
npm install
npm run dev      # 开发模式
npm run build    # 构建到 control_plane/static/
```

### 7.4 扩展开发

#### 添加新通道

1. 创建 `nanobot/channels/mychannel.py`
2. 继承 `BaseChannel`，实现 `start()`、`stop()`、`send()`
3. 在 `ChannelManager._init_channels()` 中注册

#### 添加新 Provider

1. 在 `nanobot/providers/registry.py` 添加 `ProviderSpec`
2. 在 `nanobot/config/schema.py` 的 `ProvidersConfig` 添加字段

#### 添加新工具

1. 创建 `nanobot/agent/tools/mytool.py`
2. 在 `AgentLoop._register_default_tools()` 中注册

---

## 8. CLI 命令速查

| 命令 | 说明 |
|------|------|
| `nanobot onboard` | 初始化配置和工作区 |
| `nanobot agent` | 交互式聊天 |
| `nanobot agent -m "..."` | 单条消息 |
| `nanobot agent --no-markdown` | 纯文本输出 |
| `nanobot agent --logs` | 显示运行日志 |
| `nanobot gateway` | 启动 gateway（通道 + Agent） |
| `nanobot gateway -p 8888` | 指定端口 |
| `nanobot status` | 查看状态 |
| `nanobot channels status` | 查看通道状态 |
| `nanobot channels login` | WhatsApp 扫码 |
| `nanobot cron list` | 查看定时任务 |
| `nanobot cron add ...` | 添加定时任务 |
| `nanobot cron remove <id>` | 删除定时任务 |
| `nanobot register ...` | 注册节点到 Control Plane |
| `nanobot provider login openai-codex` | OAuth 登录 |

---

## 9. 配置文件参考

配置文件路径：`~/.nanobot/config.json`

```json
{
  "agents": {
    "defaults": {
      "model": "anthropic/claude-opus-4-5",
      "temperature": 0.7,
      "max_tokens": 4096,
      "max_tool_iterations": 10,
      "memory_window": 10
    }
  },
  "providers": {
    "openrouter": { "apiKey": "" },
    "anthropic": { "apiKey": "" },
    "openai": { "apiKey": "" },
    "deepseek": { "apiKey": "" },
    "custom": { "apiKey": "", "apiBase": "" }
  },
  "channels": {
    "telegram": { "enabled": false, "token": "", "allowFrom": [] },
    "discord": { "enabled": false, "token": "", "allowFrom": [] },
    "feishu": { "enabled": false, "appId": "", "appSecret": "" },
    "whatsapp": { "enabled": false, "allowFrom": [] },
    "slack": { "enabled": false, "botToken": "", "appToken": "" },
    "dingtalk": { "enabled": false, "clientId": "", "clientSecret": "" },
    "email": { "enabled": false },
    "qq": { "enabled": false, "appId": "", "secret": "" },
    "mochat": { "enabled": false }
  },
  "tools": {
    "web": { "search": { "apiKey": "" } },
    "exec": { "enabled": true },
    "restrictToWorkspace": false,
    "mcpServers": {}
  },
  "controlPlane": {
    "url": "",
    "apiKey": "",
    "nodeId": ""
  }
}
```

---

## 10. 故障排查

| 问题 | 排查方向 |
|------|---------|
| `No API key configured` | 检查 config.json 中对应 provider 的 apiKey |
| 通道无响应 | `nanobot channels status` 检查通道状态；确认 token/凭证正确 |
| 受管模式启动失败 | 检查 controlPlane 的 url/apiKey/nodeId 是否完整 |
| 无法连接 Control Plane | 检查网络连通性；查看 Control Plane 日志 |
| 飞书消息不路由 | 确认用户已绑定到节点；检查飞书网关状态 |
| LLM 调用失败（受管模式） | 确认 Control Plane 已分配 LLM Key |
| WhatsApp 无法启动 | 确认 Node.js ≥ 18 已安装；重新 `nanobot channels login` |
| Docker 容器启动失败 | 检查 `~/.nanobot` 目录权限；查看 `docker logs` |
