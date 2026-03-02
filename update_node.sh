#!/bin/bash
# Nanobot 节点更新脚本

set -e

echo "🔄 开始更新 nanobot..."

# 获取 nanobot 安装路径
NANOBOT_PATH=$(python3 -c "import nanobot; import os; print(os.path.dirname(nanobot.__file__))" 2>/dev/null || echo "")

if [ -z "$NANOBOT_PATH" ]; then
    echo "❌ 未找到 nanobot 安装路径"
    exit 1
fi

# 找到 Git 仓库根目录
REPO_PATH=$(cd "$NANOBOT_PATH/.." && git rev-parse --show-toplevel 2>/dev/null || echo "")

if [ -z "$REPO_PATH" ]; then
    echo "❌ 未找到 Git 仓库"
    exit 1
fi

echo "📁 仓库路径: $REPO_PATH"

# 进入仓库目录
cd "$REPO_PATH"

# 保存当前分支
CURRENT_BRANCH=$(git branch --show-current)
echo "🌿 当前分支: $CURRENT_BRANCH"

# 拉取最新代码
echo "⬇️  拉取最新代码..."
git pull origin "$CURRENT_BRANCH"

# 重新安装（如果是开发模式）
if [ -f "setup.py" ] || [ -f "pyproject.toml" ]; then
    echo "📦 重新安装依赖..."
    pip install -e . --quiet
fi

echo "✅ 更新完成！"
echo ""
echo "请重启 nanobot 服务："
echo "  sudo systemctl restart nanobot"
echo "或者："
echo "  pkill -f 'nanobot gateway' && nanobot gateway"
