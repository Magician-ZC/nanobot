"""SQLite 数据库连接和迁移管理"""

from pathlib import Path

import aiosqlite

# 默认数据库路径
DEFAULT_DB_PATH = Path("data/control_plane.db")

# 当前 schema 版本
CURRENT_SCHEMA_VERSION = 1


async def get_connection(db_path: Path | None = None) -> aiosqlite.Connection:
    """获取异步 SQLite 数据库连接"""
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(db_path))
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = aiosqlite.Row
    return conn


# ── Schema V1: 所有初始表 ──────────────────────────────────────────

_SCHEMA_VERSION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'operator' CHECK (role IN ('admin', 'operator')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_NODES_TABLE = """
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    hostname TEXT NOT NULL,
    api_key_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'offline' CHECK (status IN ('online', 'offline')),
    last_heartbeat TEXT,
    config_version INTEGER NOT NULL DEFAULT 0,
    policy_version INTEGER NOT NULL DEFAULT 0,
    last_report TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_REGISTRATION_TOKENS_TABLE = """
CREATE TABLE IF NOT EXISTS registration_tokens (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    is_used INTEGER NOT NULL DEFAULT 0,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_SKILL_REGISTRY_TABLE = """
CREATE TABLE IF NOT EXISTS skill_registry (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'custom' CHECK (source IN ('builtin', 'workspace', 'custom')),
    version INTEGER NOT NULL DEFAULT 1,
    checksum TEXT NOT NULL DEFAULT '',
    package_path TEXT NOT NULL DEFAULT '',
    file_size INTEGER NOT NULL DEFAULT 0,
    uploaded_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_MCP_SERVER_REGISTRY_TABLE = """
CREATE TABLE IF NOT EXISTS mcp_server_registry (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    connection_type TEXT NOT NULL DEFAULT 'stdio' CHECK (connection_type IN ('stdio', 'http')),
    config TEXT NOT NULL DEFAULT '{}',
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_RESOURCE_POLICIES_TABLE = """
CREATE TABLE IF NOT EXISTS resource_policies (
    id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL UNIQUE REFERENCES nodes(id) ON DELETE CASCADE,
    allowed_skills TEXT NOT NULL DEFAULT '[]',
    allowed_mcp_servers TEXT NOT NULL DEFAULT '[]',
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_NODE_CONFIGS_TABLE = """
CREATE TABLE IF NOT EXISTS node_configs (
    id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL UNIQUE REFERENCES nodes(id) ON DELETE CASCADE,
    config_data TEXT NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_TASK_LOCKS_TABLE = """
CREATE TABLE IF NOT EXISTS task_locks (
    id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    resource TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    acquired_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL
);
"""

_NODE_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS node_logs (
    id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR')),
    message TEXT NOT NULL,
    extra TEXT,
    received_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_SKILL_PACKAGES_TABLE = """
CREATE TABLE IF NOT EXISTS skill_packages (
    id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL REFERENCES skill_registry(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    checksum TEXT NOT NULL,
    package_path TEXT NOT NULL,
    file_size INTEGER NOT NULL DEFAULT 0,
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_AUDIT_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    timestamp TEXT NOT NULL,
    operation_type TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '{}',
    result TEXT NOT NULL CHECK (result IN ('success', 'failed', 'denied')),
    is_violation INTEGER NOT NULL DEFAULT 0,
    received_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_LLM_KEY_POOL_TABLE = """
CREATE TABLE IF NOT EXISTS llm_key_pool (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    api_key_encrypted TEXT NOT NULL,
    max_concurrent INTEGER NOT NULL DEFAULT 5,
    current_concurrent INTEGER NOT NULL DEFAULT 0,
    usage_limit INTEGER NOT NULL DEFAULT 0,
    total_usage INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_TOKEN_USAGE_TABLE = """
CREATE TABLE IF NOT EXISTS token_usage (
    id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    key_id TEXT NOT NULL REFERENCES llm_key_pool(id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    timestamp TEXT NOT NULL,
    received_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_NODE_KEY_ASSIGNMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS node_key_assignments (
    id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    key_id TEXT NOT NULL REFERENCES llm_key_pool(id) ON DELETE CASCADE,
    assigned_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# V1 所有建表语句，按依赖顺序排列
_V1_TABLES = [
    _USERS_TABLE,
    _NODES_TABLE,
    _REGISTRATION_TOKENS_TABLE,
    _SKILL_REGISTRY_TABLE,
    _MCP_SERVER_REGISTRY_TABLE,
    _RESOURCE_POLICIES_TABLE,
    _NODE_CONFIGS_TABLE,
    _TASK_LOCKS_TABLE,
    _NODE_LOGS_TABLE,
    _SKILL_PACKAGES_TABLE,
    _AUDIT_LOGS_TABLE,
    _LLM_KEY_POOL_TABLE,
    _TOKEN_USAGE_TABLE,
    _NODE_KEY_ASSIGNMENTS_TABLE,
]

# 索引
_V1_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_nodes_user_id ON nodes(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_nodes_status ON nodes(status);",
    "CREATE INDEX IF NOT EXISTS idx_registration_tokens_user_id ON registration_tokens(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_resource_policies_node_id ON resource_policies(node_id);",
    "CREATE INDEX IF NOT EXISTS idx_node_configs_node_id ON node_configs(node_id);",
    "CREATE INDEX IF NOT EXISTS idx_task_locks_node_id ON task_locks(node_id);",
    "CREATE INDEX IF NOT EXISTS idx_task_locks_resource ON task_locks(resource);",
    "CREATE INDEX IF NOT EXISTS idx_node_logs_node_id ON node_logs(node_id);",
    "CREATE INDEX IF NOT EXISTS idx_node_logs_timestamp ON node_logs(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_node_logs_level ON node_logs(level);",
    "CREATE INDEX IF NOT EXISTS idx_audit_logs_node_id ON audit_logs(node_id);",
    "CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_audit_logs_is_violation ON audit_logs(is_violation);",
    "CREATE INDEX IF NOT EXISTS idx_token_usage_node_id ON token_usage(node_id);",
    "CREATE INDEX IF NOT EXISTS idx_token_usage_key_id ON token_usage(key_id);",
    "CREATE INDEX IF NOT EXISTS idx_token_usage_timestamp ON token_usage(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_node_key_assignments_node_id ON node_key_assignments(node_id);",
]


async def _get_schema_version(conn: aiosqlite.Connection) -> int:
    """获取当前数据库 schema 版本，不存在则返回 0"""
    try:
        cursor = await conn.execute(
            "SELECT MAX(version) FROM schema_version"
        )
        row = await cursor.fetchone()
        return row[0] if row and row[0] is not None else 0
    except Exception:
        return 0


async def _apply_v1(conn: aiosqlite.Connection) -> None:
    """应用 V1 schema：创建所有初始表和索引"""
    for table_sql in _V1_TABLES:
        await conn.execute(table_sql)
    for index_sql in _V1_INDEXES:
        await conn.execute(index_sql)


# 迁移注册表：版本号 -> 迁移函数
_MIGRATIONS: dict[int, callable] = {
    1: _apply_v1,
}


async def init_db(db_path: Path | None = None) -> None:
    """初始化数据库，创建所有表并执行迁移

    使用版本化迁移机制，每次启动时检查 schema_version 表，
    按顺序执行未应用的迁移。
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    conn = await get_connection(db_path)
    try:
        # 确保 schema_version 表存在
        await conn.execute(_SCHEMA_VERSION_TABLE)
        await conn.commit()

        current_version = await _get_schema_version(conn)

        # 按顺序执行未应用的迁移
        for version in sorted(_MIGRATIONS.keys()):
            if version > current_version:
                await _MIGRATIONS[version](conn)
                await conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (version,),
                )
                await conn.commit()
    finally:
        await conn.close()
