"""部署脚本生成 API - 动态生成 Docker/pip 一键部署命令"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from control_plane.auth import get_current_user
from control_plane.nodes import validate_registration_token

router = APIRouter()


def _get_base_url(request: Request) -> str:
    """从请求中推断 Control Plane 的外部访问地址"""
    # 优先使用 X-Forwarded 头（反向代理场景）
    forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    forwarded_host = request.headers.get("x-forwarded-host", request.headers.get("host", "localhost:8080"))
    return f"{forwarded_proto}://{forwarded_host}"


def _generate_docker_script(token_id: str, base_url: str) -> str:
    """生成 Docker 一键部署命令"""
    return (
        f"docker run -d --name nanobot \\\n"
        f"  --restart unless-stopped \\\n"
        f"  -v ~/.nanobot:/root/.nanobot \\\n"
        f"  -e NANOBOT_REGISTER_TOKEN={token_id} \\\n"
        f"  -e NANOBOT_CONTROL_PLANE_URL={base_url} \\\n"
        f"  nanobot-ai gateway"
    )


def _generate_pip_script(token_id: str, base_url: str) -> str:
    """生成 pip 安装 shell 脚本"""
    return (
        '#!/bin/bash\n'
        'set -e\n'
        '\n'
        '# ── nanobot 一键安装脚本 ──\n'
        f'NANOBOT_REGISTER_TOKEN="{token_id}"\n'
        f'NANOBOT_CONTROL_PLANE_URL="{base_url}"\n'
        '\n'
        '# 检查 Python 版本\n'
        'check_python() {\n'
        '    if command -v python3 &>/dev/null; then\n'
        '        PY=python3\n'
        '    elif command -v python &>/dev/null; then\n'
        '        PY=python\n'
        '    else\n'
        '        echo "错误: 未找到 Python，请先安装 Python 3.11+"\n'
        '        exit 1\n'
        '    fi\n'
        '    VERSION=$($PY -c "import sys; print(f\'{sys.version_info.major}.{sys.version_info.minor}\')")\n'
        '    MAJOR=$($PY -c "import sys; print(sys.version_info.major)")\n'
        '    MINOR=$($PY -c "import sys; print(sys.version_info.minor)")\n'
        '    if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 11 ]); then\n'
        '        echo "错误: 需要 Python 3.11+，当前版本为 $VERSION"\n'
        '        exit 1\n'
        '    fi\n'
        '    echo "✓ Python 版本: $VERSION"\n'
        '}\n'
        '\n'
        'check_python\n'
        '\n'
        '# 安装 nanobot\n'
        'echo "正在安装 nanobot-ai..."\n'
        '$PY -m pip install --upgrade nanobot-ai\n'
        '\n'
        '# 首次安装初始化\n'
        'if [ ! -d "$HOME/.nanobot" ]; then\n'
        '    echo "首次安装，执行初始化..."\n'
        '    nanobot onboard\n'
        'fi\n'
        '\n'
        '# 注册到 Control Plane\n'
        'echo "正在注册节点到 Control Plane..."\n'
        'if nanobot register --token "$NANOBOT_REGISTER_TOKEN" --server "$NANOBOT_CONTROL_PLANE_URL"; then\n'
        '    echo ""\n'
        '    echo "✓ 安装和注册完成！"\n'
        '    echo "  运行以下命令启动 gateway:"\n'
        '    echo "  nanobot gateway"\n'
        'else\n'
        '    echo ""\n'
        '    echo "错误: 注册失败，令牌可能已过期或已使用"\n'
        '    echo "  请联系管理员获取新的注册令牌"\n'
        '    exit 1\n'
        'fi\n'
    )


@router.get("/api/deploy/script", response_class=PlainTextResponse)
async def get_deploy_script(
    request: Request,
    token_id: str = Query(..., description="注册令牌 ID"),
    type: str = Query(..., pattern=r"^(docker|pip)$", description="部署类型: docker 或 pip"),
    _user: dict = Depends(get_current_user),
):
    """生成一键部署脚本

    根据 token_id 和 type 参数动态生成 Docker 或 pip 部署命令/脚本。
    脚本中内嵌注册令牌和 Control Plane 地址。
    """
    # 验证令牌存在且有效
    token = await validate_registration_token(token_id)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found, expired, or already used",
        )

    base_url = _get_base_url(request)

    if type == "docker":
        content = _generate_docker_script(token_id, base_url)
    else:
        content = _generate_pip_script(token_id, base_url)

    return PlainTextResponse(content=content, media_type="text/plain")
