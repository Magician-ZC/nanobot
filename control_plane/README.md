# Nanobot Control Plane

多用户分布式管理的中心化控制面板，用于管理多个 Nanobot Agent 节点。

## 功能

- 用户认证与权限管理（admin / operator）
- Agent 节点注册、心跳监控、在线状态
- 远程配置下发与策略管控
- LLM API Key 池管理与负载均衡分配
- 飞书共享网关（多节点共享一个飞书应用）
- 一键部署脚本生成（Docker / pip）
- Skill 仓库管理
- 审计日志与 Token 用量统计
- Vue.js Web 管理界面

## 独立部署

将整个 `control_plane/` 目录拷贝到目标机器的任意位置：

```bash
# 假设拷贝到 /opt/nanobot-cp/control_plane/
scp -r control_plane/ user@server:/opt/nanobot-cp/
```

### Docker 部署（推荐）

```bash
cd /opt/nanobot-cp
cp control_plane/.env.example control_plane/.env
# 编辑 .env，修改 CP_JWT_SECRET
docker compose -f control_plane/docker-compose.yml up -d
# 首次启动查看日志获取 admin 密码
docker compose -f control_plane/docker-compose.yml logs control-plane
```

### 本地部署

```bash
cd /opt/nanobot-cp
python -m venv .venv
source .venv/bin/activate
pip install fastapi "uvicorn[standard]" "python-jose[cryptography]" bcrypt aiosqlite pydantic loguru lark-oapi websockets

# 构建前端
cd control_plane/frontend && npm install && npm run build && cd ../..

# 启动
python control_plane/run.py
# 或指定端口
python control_plane/run.py --port 9090
```

首次启动会自动创建 admin 用户并在控制台输出密码，请立即记录。

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `CP_PORT` | 服务端口 | 8080 |
| `CP_JWT_SECRET` | JWT 签名密钥（生产必改） | 内置默认值 |
| `CP_DB_PATH` | 数据库文件路径 | data/control_plane.db |

## 部署 Agent 节点

在管理界面生成注册令牌后：

```bash
# Docker 一键部署
docker run -d --name nanobot \
  -v ~/.nanobot:/root/.nanobot \
  -e NANOBOT_REGISTER_TOKEN=<token> \
  -e NANOBOT_CONTROL_PLANE_URL=http://<cp_host>:8080 \
  nanobot-ai gateway
```

## 项目结构

```
control_plane/
├── run.py                # 启动入口
├── pyproject.toml        # 依赖配置
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── control_plane/        # Python 包
│   ├── app.py            # FastAPI 应用
│   ├── auth.py           # 认证
│   ├── database.py       # 数据库
│   ├── models.py         # 数据模型
│   ├── feishu_gateway.py # 飞书网关
│   ├── routes/           # API 路由
│   └── ...
├── frontend/             # Vue.js 前端源码
├── static/               # 前端构建产物
└── templates/            # 部署脚本模板
```
