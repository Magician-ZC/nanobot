"""任务锁 API 路由 - 获取锁、释放锁、列出活跃任务"""

from fastapi import APIRouter, Depends, HTTPException, status

from control_plane.auth import get_current_user
from control_plane.models import TaskLockRequest, TaskLockResponse
from control_plane.permissions import check_node_access
from control_plane.tasks import (
    acquire_task_lock,
    get_task_lock,
    list_active_locks,
    release_task_lock,
)

router = APIRouter()


@router.post(
    "/api/tasks/lock",
    response_model=TaskLockResponse,
    status_code=status.HTTP_201_CREATED,
)
async def acquire_lock_endpoint(
    req: TaskLockRequest,
    current_user: dict = Depends(get_current_user),
):
    """获取任务锁

    需要对目标节点有访问权限。同一节点同一资源已有活跃锁时返回 409。
    """
    await check_node_access(current_user, req.node_id)

    lock = await acquire_task_lock(
        node_id=req.node_id,
        resource=req.resource,
        description=req.description,
        timeout_minutes=req.timeout_minutes,
    )
    if lock is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Resource is already locked on this node",
        )
    return TaskLockResponse(**lock)


@router.delete("/api/tasks/lock/{lock_id}", status_code=status.HTTP_204_NO_CONTENT)
async def release_lock_endpoint(
    lock_id: str,
    current_user: dict = Depends(get_current_user),
):
    """释放任务锁

    需要对锁所属节点有访问权限。
    """
    # 先查询锁，验证节点访问权限
    lock = await get_task_lock(lock_id)
    if not lock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task lock not found",
        )
    await check_node_access(current_user, lock["node_id"])

    await release_task_lock(lock_id)


@router.get("/api/tasks", response_model=list[TaskLockResponse])
async def list_tasks_endpoint(
    node_id: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    """列出活跃任务锁

    admin 可查看所有，operator 只能查看自己节点的锁。
    可通过 node_id 查询参数过滤。
    """
    if node_id:
        await check_node_access(current_user, node_id)
        locks = await list_active_locks(node_id=node_id)
    elif current_user["role"] == "admin":
        locks = await list_active_locks()
    else:
        # operator 只能看自己节点的锁 - 先获取自己的节点列表
        from control_plane.nodes import list_nodes
        user_nodes = await list_nodes(user_id=current_user["id"])
        locks = []
        for node in user_nodes:
            node_locks = await list_active_locks(node_id=node["id"])
            locks.extend(node_locks)

    return [TaskLockResponse(**lock) for lock in locks]
