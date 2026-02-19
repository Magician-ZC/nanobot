"""权限检查中间件 - 节点访问控制"""

from fastapi import Depends, HTTPException, Request, status

from control_plane.auth import get_current_user
from control_plane.database import get_connection


async def check_node_access(user: dict, node_id: str) -> dict:
    """检查用户是否有权访问指定节点

    - admin: 允许访问所有节点
    - operator: 仅允许访问自己拥有的节点

    Args:
        user: 当前用户字典（含 id, role 等字段）
        node_id: 目标节点 ID

    Returns:
        节点记录字典

    Raises:
        HTTPException 404: 节点不存在
        HTTPException 403: operator 无权访问他人节点
    """
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, user_id, hostname, status, last_heartbeat, "
            "config_version, policy_version, last_report, created_at "
            "FROM nodes WHERE id = ?",
            (node_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Node not found",
            )

        node = {
            "id": row[0],
            "user_id": row[1],
            "hostname": row[2],
            "status": row[3],
            "last_heartbeat": row[4],
            "config_version": row[5],
            "policy_version": row[6],
            "last_report": row[7],
            "created_at": row[8],
        }

        # admin 允许访问所有节点
        if user["role"] == "admin":
            return node

        # 节点自身认证：只能访问自己的数据
        if user["role"] == "node":
            if user.get("node_id") != node_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: node can only access its own data",
                )
            return node

        # operator 仅允许访问自己的节点
        if node["user_id"] != user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: you can only access your own nodes",
            )

        return node
    finally:
        await conn.close()


async def require_node_access(
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """FastAPI 依赖注入：验证当前用户对路径中 node_id 的访问权限

    从路径参数中提取 node_id（支持 'id' 和 'node_id' 两种命名），
    然后调用 check_node_access 进行权限检查。

    Returns:
        包含 "user" 和 "node" 的字典
    """
    # 从路径参数中提取 node_id
    node_id = request.path_params.get("id") or request.path_params.get("node_id")
    if not node_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Node ID is required in path",
        )

    node = await check_node_access(current_user, node_id)
    return {"user": current_user, "node": node}
