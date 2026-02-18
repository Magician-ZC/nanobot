"""认证 API 路由"""

from fastapi import APIRouter, Depends, HTTPException, status

from control_plane.auth import (
    authenticate_user,
    create_access_token,
    create_user,
    disable_user,
    list_users,
    require_admin,
    update_user,
    get_user_by_id,
)
from control_plane.models import (
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)

router = APIRouter()


@router.post("/api/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """用户登录，返回 JWT 令牌"""
    user = await authenticate_user(req.username, req.password)
    if not user:
        # 不区分"用户不存在"和"密码错误"，统一返回相同错误
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token(user["id"], user["role"])
    return TokenResponse(access_token=token)


@router.post("/api/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user_endpoint(req: UserCreate, _admin: dict = Depends(require_admin)):
    """创建用户（仅 admin）"""
    user = await create_user(req.username, req.password, req.role)
    return UserResponse(**user)


@router.get("/api/users", response_model=list[UserResponse])
async def list_users_endpoint(_admin: dict = Depends(require_admin)):
    """列出所有用户（仅 admin）"""
    users = await list_users()
    return [UserResponse(**u) for u in users]


@router.put("/api/users/{user_id}", response_model=UserResponse)
async def update_user_endpoint(
    user_id: str, req: UserUpdate, _admin: dict = Depends(require_admin)
):
    """更新用户信息（仅 admin）"""
    update_data = req.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    user = await update_user(user_id, **update_data)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse(**user)


@router.delete("/api/users/{user_id}", response_model=UserResponse)
async def disable_user_endpoint(user_id: str, _admin: dict = Depends(require_admin)):
    """禁用用户（仅 admin，软删除）"""
    user = await disable_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse(**user)
