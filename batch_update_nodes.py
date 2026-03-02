#!/usr/bin/env python3
"""批量更新远程 nanobot 节点"""

import asyncio
import sys
from pathlib import Path

import aiohttp


async def get_online_nodes(control_plane_url: str, api_key: str) -> list[dict]:
    """从 Control Plane 获取在线节点列表"""
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {api_key}"}
        async with session.get(f"{control_plane_url}/api/nodes", headers=headers) as resp:
            if resp.status != 200:
                print(f"❌ 获取节点列表失败: {resp.status}")
                return []
            data = await resp.json()
            return [n for n in data if n.get("status") == "online"]


async def update_node_via_ssh(hostname: str, ssh_user: str = "root"):
    """通过 SSH 更新节点"""
    print(f"🔄 更新节点: {hostname}")
    
    # SSH 命令
    update_cmd = """
    cd $(python3 -c "import nanobot, os; print(os.path.dirname(os.path.dirname(nanobot.__file__)))" 2>/dev/null) && \
    git pull && \
    pip install -e . --quiet && \
    echo "✅ 更新完成，请重启服务"
    """
    
    proc = await asyncio.create_subprocess_exec(
        "ssh", f"{ssh_user}@{hostname}", update_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await proc.communicate()
    
    if proc.returncode == 0:
        print(f"✅ {hostname}: 更新成功")
        print(stdout.decode())
    else:
        print(f"❌ {hostname}: 更新失败")
        print(stderr.decode())


async def main():
    if len(sys.argv) < 3:
        print("用法: python batch_update_nodes.py <control_plane_url> <api_key> [ssh_user]")
        print("示例: python batch_update_nodes.py http://localhost:8000 your-api-key root")
        sys.exit(1)
    
    control_plane_url = sys.argv[1]
    api_key = sys.argv[2]
    ssh_user = sys.argv[3] if len(sys.argv) > 3 else "root"
    
    print("📡 获取在线节点列表...")
    nodes = await get_online_nodes(control_plane_url, api_key)
    
    if not nodes:
        print("❌ 没有在线节点")
        return
    
    print(f"找到 {len(nodes)} 个在线节点")
    
    # 批量更新
    tasks = [update_node_via_ssh(node["hostname"], ssh_user) for node in nodes]
    await asyncio.gather(*tasks)
    
    print("\n✅ 批量更新完成！")
    print("⚠️  请手动重启各节点的 nanobot 服务")


if __name__ == "__main__":
    asyncio.run(main())
