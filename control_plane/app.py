"""FastAPI 应用入口 - Control Plane Web 服务"""

import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from control_plane.database import init_db
from control_plane.routes.audit import router as audit_router
from control_plane.routes.auth import router as auth_router
from control_plane.routes.deploy import router as deploy_router
from control_plane.routes.llm_keys import router as llm_keys_router
from control_plane.routes.logs import router as logs_router
from control_plane.routes.nodes import router as nodes_router
from control_plane.routes.policies import router as policies_router
from control_plane.routes.skill_store import router as skill_store_router
from control_plane.routes.feishu_gateway import (
    router as feishu_gateway_router,
    set_gateway_service,
    set_message_router,
)
from control_plane.routes.tasks import router as tasks_router
from control_plane.feishu_gateway import FeishuGatewayService
from control_plane.feishu_router import MessageRouter


async def _ensure_admin_user() -> None:
    """首次启动时自动创建 admin 用户（如果不存在）"""
    from control_plane.auth import get_user_by_username, create_user

    existing = await get_user_by_username("admin")
    if existing:
        return

    password = secrets.token_urlsafe(16)
    await create_user("admin", password, "admin")
    # 输出到控制台，仅首次可见
    print("=" * 50)
    print("  首次启动：已自动创建 admin 用户")
    print(f"  用户名: admin")
    print(f"  密码: {password}")
    print("  请登录后立即修改密码！")
    print("=" * 50)


def create_app(db_path: Path | None = None) -> FastAPI:
    """创建并配置 FastAPI 应用实例

    Args:
        db_path: 数据库文件路径，None 则使用默认路径
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 启动时初始化数据库并确保 admin 用户存在
        await init_db(db_path)
        await _ensure_admin_user()

        # 初始化飞书网关服务和消息路由器
        gateway_service = FeishuGatewayService()
        message_router = MessageRouter(gateway_service=gateway_service)
        gateway_service.set_message_callback(message_router.route_inbound)
        set_gateway_service(gateway_service)
        set_message_router(message_router)

        yield

        # 关闭时停止网关
        await gateway_service.stop()

    app = FastAPI(
        title="Nanobot Control Plane",
        description="多用户分布式管理的中心化控制面板",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(audit_router)
    app.include_router(auth_router)
    app.include_router(deploy_router)
    app.include_router(llm_keys_router)
    app.include_router(logs_router)
    app.include_router(nodes_router)
    app.include_router(policies_router)
    app.include_router(skill_store_router)
    app.include_router(tasks_router)
    app.include_router(feishu_gateway_router)

    # 挂载前端静态文件（构建产物）
    _mount_frontend(app)

    return app

def _mount_frontend(app: FastAPI) -> None:
    """挂载前端静态文件并配置 SPA 路由回退"""
    static_dir = Path(__file__).parent / "static"
    if not static_dir.is_dir():
        return  # 前端未构建时跳过

    index_html = static_dir / "index.html"

    # 挂载静态资源（js/css/assets）
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

    # SPA 路由回退：非 /api 路径都返回 index.html
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # /api 开头的路径不走 SPA 回退
        if full_path.startswith("api/"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="API not found")
        # 尝试返回静态文件
        file_path = static_dir / full_path
        if full_path and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(index_html))
