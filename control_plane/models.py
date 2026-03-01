"""Pydantic 数据模型 - 请求/响应模型和数据传输对象"""

from datetime import datetime

from pydantic import BaseModel, Field


# ── User 模型 ──────────────────────────────────────────────────────

class UserCreate(BaseModel):
    """创建用户请求"""
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    role: str = Field(default="operator", pattern=r"^(admin|operator)$")


class UserUpdate(BaseModel):
    """更新用户请求"""
    username: str | None = Field(default=None, min_length=1, max_length=64)
    password: str | None = Field(default=None, min_length=6, max_length=128)
    role: str | None = Field(default=None, pattern=r"^(admin|operator)$")
    is_active: bool | None = None


class UserResponse(BaseModel):
    """用户响应"""
    id: str
    username: str
    role: str
    is_active: bool
    created_at: str
    updated_at: str


# ── Node 模型 ──────────────────────────────────────────────────────

class NodeResponse(BaseModel):
    """节点响应"""
    id: str
    user_id: str
    hostname: str
    status: str
    heartbeat_online: bool = False
    gateway_ws_connected: bool = False
    last_heartbeat: str | None = None
    config_version: int
    policy_version: int
    last_report: dict | None = None
    created_at: str


# ── Registration Token 模型 ────────────────────────────────────────

class RegistrationTokenCreate(BaseModel):
    """生成注册令牌请求"""
    user_id: str


class RegistrationTokenResponse(BaseModel):
    """注册令牌响应"""
    id: str
    user_id: str
    is_used: bool
    expires_at: str
    created_at: str


class NodeRegisterRequest(BaseModel):
    """节点注册请求"""
    token: str
    hostname: str


class NodeRegisterResponse(BaseModel):
    """节点注册响应"""
    node_id: str
    api_key: str


# ── Skill 模型 ─────────────────────────────────────────────────────

class SkillEntryCreate(BaseModel):
    """注册 Skill 请求"""
    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""
    source: str = Field(default="custom", pattern=r"^(builtin|workspace|custom)$")


class SkillEntryResponse(BaseModel):
    """Skill 注册表响应"""
    id: str
    name: str
    description: str
    source: str
    version: int
    checksum: str
    file_size: int
    created_at: str


class SkillEntryUpdate(BaseModel):
    """更新 Skill 请求"""
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    source: str | None = Field(default=None, pattern=r"^(builtin|workspace|custom)$")




class SkillPackageResponse(BaseModel):
    """Skill 包上传响应"""
    skill_id: str
    name: str
    version: int
    checksum: str
    file_size: int
    package_path: str
    uploaded_at: str


class SkillVersionResponse(BaseModel):
    """Skill 版本记录"""
    id: str
    version: int
    checksum: str
    file_size: int
    uploaded_at: str


class SkillVersionsListResponse(BaseModel):
    """Skill 版本历史列表"""
    name: str
    versions: list[SkillVersionResponse]


# ── MCP Server 模型 ────────────────────────────────────────────────

class MCPServerEntryCreate(BaseModel):
    """注册 MCP Server 请求"""
    name: str = Field(..., min_length=1, max_length=128)
    connection_type: str = Field(default="stdio", pattern=r"^(stdio|http)$")
    config: dict = Field(default_factory=dict)
    description: str = ""


class MCPServerEntryResponse(BaseModel):
    """MCP Server 注册表响应"""
    id: str
    name: str
    connection_type: str
    config: dict
    description: str
    created_at: str


class MCPServerEntryUpdate(BaseModel):
    """更新 MCP Server 请求"""
    name: str | None = Field(default=None, min_length=1, max_length=128)
    connection_type: str | None = Field(default=None, pattern=r"^(stdio|http)$")
    config: dict | None = None
    description: str | None = None




# ── Resource Policy 模型 ───────────────────────────────────────────

class ResourcePolicyUpdate(BaseModel):
    """更新节点策略请求"""
    allowed_skills: list[str] = Field(default_factory=list)
    allowed_mcp_servers: list[str] = Field(default_factory=list)


class ResourcePolicyResponse(BaseModel):
    """节点策略响应"""
    id: str
    node_id: str
    allowed_skills: list[str]
    allowed_mcp_servers: list[str]
    version: int
    updated_at: str
    skill_versions: dict[str, dict] = Field(default_factory=dict)


# ── Node Config 模型 ───────────────────────────────────────────────

class NodeConfigUpdate(BaseModel):
    """更新节点配置请求"""
    config_data: dict


class NodeConfigResponse(BaseModel):
    """节点配置响应"""
    id: str
    node_id: str
    config_data: dict
    version: int
    updated_at: str


# ── Task Lock 模型 ─────────────────────────────────────────────────

class TaskLockRequest(BaseModel):
    """获取任务锁请求"""
    node_id: str
    resource: str
    description: str = ""
    timeout_minutes: int = Field(default=10, ge=1, le=1440)


class TaskLockResponse(BaseModel):
    """任务锁响应"""
    id: str
    node_id: str
    resource: str
    description: str
    acquired_at: str
    expires_at: str


# ── 心跳 DTO ──────────────────────────────────────────────────────

class NodeStatus(BaseModel):
    """Agent Node 心跳上报的状态数据"""
    node_id: str
    loaded_skills: list[str] = Field(default_factory=list)
    connected_mcp_servers: list[str] = Field(default_factory=list)
    active_tasks: list[str] = Field(default_factory=list)
    config_version: int = 0
    policy_version: int = 0


class HeartbeatResponse(BaseModel):
    """Control Plane 心跳响应"""
    has_policy_update: bool = False
    has_config_update: bool = False
    latest_policy_version: int = 0
    latest_config_version: int = 0
    has_skill_update: bool = False


# ── 认证 DTO ──────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """JWT 令牌响应"""
    access_token: str
    token_type: str = "bearer"


# ── LLM Key 模型 ──────────────────────────────────────────────────

class LLMKeyCreate(BaseModel):
    """添加 LLM API Key 请求"""
    name: str = Field(..., min_length=1, max_length=128)
    provider: str = Field(..., min_length=1, max_length=64)
    api_key: str = Field(..., min_length=1)
    max_concurrent: int = Field(default=5, ge=1)
    usage_limit: int = Field(default=0, ge=0)


class LLMKeyUpdate(BaseModel):
    """更新 LLM Key 配置请求"""
    name: str | None = None
    max_concurrent: int | None = Field(default=None, ge=1)
    usage_limit: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class LLMKeyResponse(BaseModel):
    """LLM Key 响应（隐藏实际 Key 值）"""
    id: str
    name: str
    provider: str
    api_key_preview: str
    max_concurrent: int
    current_concurrent: int
    usage_limit: int
    total_usage: int
    is_active: bool
    created_at: str


class LLMNodeAssignmentRequest(BaseModel):
    """手动分配 LLM Key 到节点请求"""
    key_id: str = Field(..., min_length=1)
    replace_existing: bool = False


class LLMNodeAssignmentResponse(BaseModel):
    """节点 LLM Key 分配响应"""
    node_id: str
    key_id: str
    provider: str
    replaced: bool = False
    idempotent: bool = False


# ── Token 用量模型 ────────────────────────────────────────────────

class TokenUsageRecord(BaseModel):
    """单次 LLM 调用的 Token 用量"""
    timestamp: str
    model: str
    key_id: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class TokenUsageBatchRequest(BaseModel):
    """批量上报 Token 用量请求"""
    records: list[TokenUsageRecord]


class TokenUsageResponse(BaseModel):
    """Token 用量查询响应"""
    id: str
    node_id: str
    key_id: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    timestamp: str
    received_at: str


class TokenUsageSummary(BaseModel):
    """Token 用量汇总"""
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    record_count: int = 0


class RateLimitReport(BaseModel):
    """节点限流上报请求"""
    key_id: str



# ── 飞书网关模型 ──────────────────────────────────────────────────

class FeishuGatewayConfigCreate(BaseModel):
    """设置飞书网关配置请求"""
    app_id: str = Field(..., min_length=1)
    app_secret: str = Field(..., min_length=1)
    encrypt_key: str = ""
    verification_token: str = ""


class FeishuGatewayConfigResponse(BaseModel):
    """飞书网关配置响应（凭证脱敏）"""
    id: str
    app_id: str
    app_secret_preview: str
    encrypt_key_preview: str
    is_active: bool
    created_at: str
    updated_at: str


class GatewayStatusResponse(BaseModel):
    """飞书网关运行状态"""
    is_connected: bool
    connected_since: str | None = None
    last_message_at: str | None = None
    connected_nodes: int = 0
    total_bindings: int = 0


class BindingCreate(BaseModel):
    """创建飞书用户绑定请求"""
    feishu_open_id: str = Field(..., min_length=1)
    node_id: str = Field(..., min_length=1)
    feishu_name: str = ""


class BindingResponse(BaseModel):
    """飞书用户绑定响应"""
    id: str
    feishu_open_id: str
    feishu_name: str
    node_id: str
    node_hostname: str = ""
    created_at: str
    updated_at: str


class BindCodeCreate(BaseModel):
    """生成绑定码请求"""
    node_id: str = Field(..., min_length=1)
    expires_minutes: int = Field(default=30, ge=1, le=1440)


class BindCodeResponse(BaseModel):
    """绑定码响应"""
    id: str
    code: str
    node_id: str
    is_used: bool
    expires_at: str
    created_at: str


class ConversationMessageResponse(BaseModel):
    """对话记录响应"""
    id: str
    feishu_open_id: str
    node_id: str | None = None
    direction: str
    content: str
    msg_type: str
    status: str
    created_at: str

class SessionResponse(BaseModel):
    """会话列表响应（按用户分组）"""
    feishu_open_id: str
    feishu_name: str = ""
    message_count: int
    last_message_at: str
    node_id: str | None = None

