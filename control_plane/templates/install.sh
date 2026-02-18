#!/bin/bash
# ── nanobot 一键安装与注册脚本 ──
# 此脚本由 Control Plane 动态生成，内嵌注册令牌和服务器地址。
# 用法: curl -sSL <control_plane_url>/api/deploy/script?token_id=<id>&type=pip | bash

set -e

# ── 配置（由 Control Plane 动态填充） ──
NANOBOT_REGISTER_TOKEN="${NANOBOT_REGISTER_TOKEN:-__TOKEN__}"
NANOBOT_CONTROL_PLANE_URL="${NANOBOT_CONTROL_PLANE_URL:-__SERVER_URL__}"

# ── 颜色输出 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}✓${NC} $1"; }
warn()  { echo -e "${YELLOW}⚠${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; }

# ── 清理函数（令牌无效时调用） ──
cleanup_on_failure() {
    error "安装未完成，正在清理..."
    # 不删除已安装的包，仅提示用户
    error "请联系管理员获取新的注册令牌"
    exit 1
}

# ── 1. 检查 Python 版本 ──
check_python() {
    if command -v python3 &>/dev/null; then
        PY=python3
    elif command -v python &>/dev/null; then
        PY=python
    else
        error "未找到 Python，请先安装 Python 3.11+"
        exit 1
    fi

    VERSION=$($PY -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    MAJOR=$($PY -c "import sys; print(sys.version_info.major)")
    MINOR=$($PY -c "import sys; print(sys.version_info.minor)")

    if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 11 ]); then
        error "需要 Python 3.11+，当前版本为 $VERSION"
        exit 1
    fi
    info "Python 版本: $VERSION"
}

# ── 2. 安装 nanobot ──
install_nanobot() {
    echo ""
    echo "正在安装 nanobot-ai..."
    $PY -m pip install --upgrade nanobot-ai
    info "nanobot-ai 安装完成"
}

# ── 3. 首次初始化 ──
run_onboard() {
    if [ ! -d "$HOME/.nanobot" ]; then
        echo ""
        echo "首次安装，执行初始化..."
        nanobot onboard
        info "初始化完成"
    else
        info "检测到已有配置目录，跳过初始化"
    fi
}

# ── 4. 注册到 Control Plane ──
register_node() {
    echo ""
    echo "正在注册节点到 Control Plane..."
    if nanobot register --token "$NANOBOT_REGISTER_TOKEN" --server "$NANOBOT_CONTROL_PLANE_URL"; then
        info "节点注册成功"
    else
        cleanup_on_failure
    fi
}

# ── 主流程 ──
echo "═══════════════════════════════════════"
echo "  nanobot 一键安装脚本"
echo "  Control Plane: $NANOBOT_CONTROL_PLANE_URL"
echo "═══════════════════════════════════════"
echo ""

check_python
install_nanobot
run_onboard
register_node

echo ""
echo "═══════════════════════════════════════"
info "安装和注册全部完成！"
echo "  运行以下命令启动 gateway:"
echo "  nanobot gateway"
echo "═══════════════════════════════════════"
