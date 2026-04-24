#!/bin/bash
# setup.sh - 单机版一键部署脚本

set -e

echo "========================================="
echo "  Skill Factory 单机版 - 部署脚本"
echo "========================================="

# 检查 Python
if ! command -v python3 &>/dev/null; then
    echo "❌ 需要 Python 3"
    exit 1
fi

# 检查 requests
if ! python3 -c "import requests" 2>/dev/null; then
    echo "📦 安装 requests..."
    pip3 install requests
fi

# 检查 Git
if ! command -v git &>/dev/null; then
    echo "📦 安装 git..."
    apt-get install -y git
fi

# 创建 Skills 目录
SKILLS_DIR="/root/.openclaw/workspace/skills"
mkdir -p "$SKILLS_DIR"
chmod 755 "$SKILLS_DIR"
echo "✅ Skills 目录: $SKILLS_DIR"

# 初始化 Git（如果没有）
if [ ! -d "/root/.openclaw/workspace/.git" ]; then
    echo "📦 初始化 Git 仓库..."
    cd /root/.openclaw/workspace
    git init
    git config user.email "skill-factory@openclaw"
    git config user.name "Skill Factory"
    echo "✅ Git 初始化完成"
fi

# 复制脚本到工作目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cp "$SCRIPT_DIR/scripts/skill_judge.py" /root/.openclaw/workspace/scripts/skill_judge.py
chmod +x /root/.openclaw/workspace/scripts/skill_judge.py

echo ""
echo "========================================="
echo "  ✅ 部署完成！"
echo "========================================="
echo ""
echo "快速测试："
echo "  python3 /root/.openclaw/workspace/scripts/skill_judge.py '帮我分析英国电商市场'"
echo ""
echo "设置 Webhook（可选）："
echo '  export FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"'
echo ""
