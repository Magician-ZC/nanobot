"""用户管理和 JWT 认证模块"""

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from control_plane.database import get_connection, DEFAULT_DB_PATH

# JWT 配置
SECRET_KEY = "nanobot-control-plane-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

_security = HTTPBearer()


# ── 密码哈希 ──────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """使用 bcrypt 哈希密码"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码是否匹配"""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


# ── JWT 令牌 ──────────────────────────────────────────────────────

def create_access_token(user_id: str, role: str, expires_delta: timedelta | None = None) -> str:
    """生成 JWT 访问令牌"""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """解码并验证 JWT 令牌，失败抛出 HTTPException 401"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# ── 用户 CRUD ─────────────────────────────────────────────────────

async def create_user(username: str, password: str, role: str = "operator") -> dict:
    """创建用户，返回用户字典"""
    conn = await get_connection()
    try:
        # 检查用户名是否已存在
        cursor = await conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        )
        if await cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists",
            )

        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        pw_hash = hash_password(password)

        await conn.execute(
            """INSERT INTO users (id, username, password_hash, role, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, 1, ?, ?)""",
            (user_id, username, pw_hash, role, now, now),
        )
        await conn.commit()

        return {
            "id": user_id,
            "username": username,
            "role": role,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
    finally:
        await conn.close()


async def get_user_by_username(username: str) -> dict | None:
    """根据用户名查询用户"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, username, password_hash, role, is_active, created_at, updated_at "
            "FROM users WHERE username = ?",
            (username,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "username": row[1],
            "password_hash": row[2],
            "role": row[3],
            "is_active": bool(row[4]),
            "created_at": row[5],
            "updated_at": row[6],
        }
    finally:
        await conn.close()


async def get_user_by_id(user_id: str) -> dict | None:
    """根据 ID 查询用户"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, username, password_hash, role, is_active, created_at, updated_at "
            "FROM users WHERE id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "username": row[1],
            "password_hash": row[2],
            "role": row[3],
            "is_active": bool(row[4]),
            "created_at": row[5],
            "updated_at": row[6],
        }
    finally:
        await conn.close()


async def list_users() -> list[dict]:
    """列出所有用户"""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, username, role, is_active, created_at, updated_at FROM users ORDER BY created_at"
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": row[0],
                "username": row[1],
                "role": row[2],
                "is_active": bool(row[3]),
                "created_at": row[4],
                "updated_at": row[5],
            }
            for row in rows
        ]
    finally:
        await conn.close()


async def update_user(user_id: str, **kwargs) -> dict | None:
    """更新用户信息，返回更新后的用户字典"""
    conn = await get_connection()
    try:
        # 先检查用户是否存在
        user = await get_user_by_id(user_id)
        if not user:
            return None

        now = datetime.now(timezone.utc).isoformat()
        sets = ["updated_at = ?"]
        params: list = [now]

        if "username" in kwargs and kwargs["username"] is not None:
            # 检查新用户名是否冲突
            cursor = await conn.execute(
                "SELECT id FROM users WHERE username = ? AND id != ?",
                (kwargs["username"], user_id),
            )
            if await cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username already exists",
                )
            sets.append("username = ?")
            params.append(kwargs["username"])

        if "password" in kwargs and kwargs["password"] is not None:
            sets.append("password_hash = ?")
            params.append(hash_password(kwargs["password"]))

        if "role" in kwargs and kwargs["role"] is not None:
            sets.append("role = ?")
            params.append(kwargs["role"])

        if "is_active" in kwargs and kwargs["is_active"] is not None:
            sets.append("is_active = ?")
            params.append(1 if kwargs["is_active"] else 0)

        params.append(user_id)
        await conn.execute(
            f"UPDATE users SET {', '.join(sets)} WHERE id = ?", params
        )
        await conn.commit()

        return await get_user_by_id(user_id)
    finally:
        await conn.close()


async def disable_user(user_id: str) -> dict | None:
    """禁用用户（软删除）"""
    return await update_user(user_id, is_active=False)


# ── 认证逻辑 ──────────────────────────────────────────────────────

async def authenticate_user(username: str, password: str) -> dict | None:
    """验证用户凭据，成功返回用户字典，失败返回 None"""
    user = await get_user_by_username(username)
    if not user:
        return None
    if not user["is_active"]:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


# ── FastAPI 依赖注入 ──────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> dict:
    """FastAPI 依赖：从 JWT 令牌获取当前用户"""
    payload = decode_access_token(credentials.credentials)
    user_id = payload["sub"]
    user = await get_user_by_id(user_id)
    if not user or not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or disabled",
        )
    return user


async def require_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """FastAPI 依赖：要求当前用户为 admin 角色"""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def get_current_user_or_node(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> dict:
    """FastAPI 依赖：先尝试 JWT 用户认证，失败后尝试节点 API Key 认证

    节点认证时 Bearer token 格式为 "{api_key}"，
    返回 {"id": node_id, "role": "node", "node_id": node_id}
    """
    token = credentials.credentials

    # 1. 先尝试 JWT 认证
    try:
        payload = decode_access_token(token)
        user_id = payload["sub"]
        user = await get_user_by_id(user_id)
        if user and user["is_active"]:
            return user
    except HTTPException:
        pass

    # 2. JWT 失败，尝试节点 API Key 认证
    from control_plane.nodes import verify_node_api_key_only
    node = await verify_node_api_key_only(token)
    if node:
        return {"id": node["id"], "role": "node", "node_id": node["id"]}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
    )
