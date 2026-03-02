"""Docker 自动注册引导 - 容器首次启动时自动注册到 Control Plane"""

import logging
import os
import platform

logger = logging.getLogger(__name__)


async def auto_register_if_needed() -> bool:
    """检测环境变量或 config.json，首次启动时自动注册到 Control Plane。

    优先检查环境变量 NANOBOT_REGISTER_TOKEN 和 NANOBOT_CONTROL_PLANE_URL，
    如果环境变量不存在，则从 config.json 中读取 controlPlane.registerToken 和 controlPlane.url。
    如果存在且节点尚未注册，则自动执行注册流程。

    Returns:
        True 如果执行了注册（或已注册），False 如果无需注册。
    """
    # 优先从环境变量读取
    token = os.environ.get("NANOBOT_REGISTER_TOKEN")
    server_url = os.environ.get("NANOBOT_CONTROL_PLANE_URL")

    # 如果环境变量不存在，从 config.json 读取
    if not token or not server_url:
        from nanobot.config.loader import load_config
        config = load_config()
        if not token:
            token = config.control_plane.register_token
        if not server_url:
            server_url = config.control_plane.url

    if not token or not server_url:
        return False

    from nanobot.config.loader import load_config, save_config

    config = load_config()

    # 已注册则跳过
    if config.control_plane.node_id and config.control_plane.api_key:
        logger.info("节点已注册，跳过自动注册")
        return True

    # 执行注册
    hostname = platform.node() or "unknown"
    logger.info("检测到注册环境变量，开始自动注册到 %s", server_url)

    from nanobot.managed.client import ManagedClient, ControlPlaneError

    client = ManagedClient(control_plane_url=server_url)
    try:
        result = await client.register(token=token, hostname=hostname)
    except ControlPlaneError as e:
        logger.error("自动注册失败: %s", e)
        return False
    finally:
        await client.close()

    # 持久化配置
    config.control_plane.url = server_url
    config.control_plane.api_key = result["api_key"]
    config.control_plane.node_id = result["node_id"]
    save_config(config)

    # 创建受管标记文件
    from nanobot.managed.marker import ManagedMarker
    ManagedMarker().create(server_url)

    logger.info("自动注册成功，Node ID: %s", result["node_id"])
    return True
