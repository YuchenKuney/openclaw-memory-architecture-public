#!/bin/bash
# =============================================================================
# OpenClaw Memory Architecture - 一键安装脚本
# =============================================================================
#
# 🦐 开源项目 · 欢迎共建
#
# 如果你觉得这个项目有帮助，欢迎：
#   ⭐ Star → https://github.com/YuchenKuney/openclaw-memory-architecture-public
#   🐛 提 Issue → 发现 Bug 或有新功能建议
#   🤝 提 PR → 直接贡献代码
#
# 优秀建议和贡献者将加入 CONTRIBUTORS.md 荣誉榜！
#   → https://github.com/YuchenKuney/openclaw-memory-architecture-public/blob/main/CONTRIBUTORS.md
#
# =============================================================================

set -e

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()  { echo -e "${GREEN}[OK]${NC} $1"; }
warn(){ echo -e "${YELLOW}[WARN]${NC} $1"; }
err() { echo -e "${RED}[ERROR]${NC} $1"; }

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  🦐 OpenClaw Memory Architecture - 一键安装"
echo "═══════════════════════════════════════════════════════"
echo ""

# =============================================================================
# 1. 系统检测
# =============================================================================
log "检测系统环境..."

if [[ "$EUID" -ne 0 ]]; then
    warn "建议使用 root 用户运行，以获得最佳体验"
fi

if ! command -v python3 &> /dev/null; then
    err "Python3 未安装，请先安装 Python3.8+"
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
log "Python 版本: $PY_VERSION"

# =============================================================================
# 2. 克隆仓库（如果不在仓库目录）
# =============================================================================
if [ ! -f "demo.py" ] && [ ! -f "AGENTS.md" ]; then
    log "检测到未在仓库目录，正在克隆..."
    read -p "请输入仓库路径（如 /root/openclaw-memory）: " REPO_PATH
    if [ -z "$REPO_PATH" ]; then
        REPO_PATH="/root/openclaw-memory"
    fi
    
    if [ -d "$REPO_PATH" ]; then
        warn "目录已存在，将进入现有目录"
    else
        git clone https://github.com/YuchenKuney/openclaw-memory-architecture-public.git "$REPO_PATH"
    fi
    cd "$REPO_PATH"
fi

WORKSPACE=$(pwd)
ok "工作目录: $WORKSPACE"

# =============================================================================
# 3. 安装依赖
# =============================================================================
log "安装 Python 依赖..."

# 核心依赖
pip3 install --upgrade pip -q

# OpenClaw（核心框架）
pip3 install openclaw -q 2>/dev/null || warn "OpenClaw 安装失败，请参考 https://docs.openclaw.ai"

# 核心依赖
pip3 install pydantic aiohttp inotify-tools watchdog -q 2>/dev/null || true

ok "依赖安装完成"

# =============================================================================
# 4. 初始化目录结构
# =============================================================================
log "初始化目录结构..."

mkdir -p memory
mkdir -p clawkeeper/backup
mkdir -p scripts
mkdir -p demo/outputs
mkdir -p logs

ok "目录初始化完成"

# =============================================================================
# 5. 飞书配置（可选）
# =============================================================================
echo ""
echo "───────────────────────────────────────────────────────"
echo "  飞书配置（可选，跳过可稍后手动配置）"
echo "───────────────────────────────────────────────────────"
read -p "输入飞书 APP_ID（留空跳过）: " FEISHU_APP_ID
read -p "输入飞书 APP_SECRET（留空跳过）: " FEISHU_APP_SECRET

if [ -n "$FEISHU_APP_ID" ] && [ -n "$FEISHU_APP_SECRET" ]; then
    cat > .env << EOF
FEISHU_APP_ID=$FEISHU_APP_ID
FEISHU_APP_SECRET=$FEISHU_APP_SECRET
EOF
    ok "飞书配置已保存到 .env"
else
    warn "跳过飞书配置，相关功能将在配置后生效"
fi

# =============================================================================
# 6. 设置定时任务
# =============================================================================
log "设置定时任务..."

# 读取现有 crontab
CRON_TEMP=$(mktemp)

# 添加任务（如果不存在）
add_cron() {
    local EXPR=$1
    local CMD=$2
    local DESC=$3
    
    if crontab -l 2>/dev/null | grep -q "$CMD"; then
        warn "定时任务已存在: $DESC"
    else
        (crontab -l 2>/dev/null; echo "$EXPR $CMD # $DESC") | crontab -
        ok "添加定时任务: $DESC"
    fi
}

# 每日记忆蒸馏（18:30）
add_cron "30 18 * * *" "cd $WORKSPACE && python3 scripts/log_distiller.py >> logs/distill.log 2>&1" "记忆蒸馏"

# 看门狗（开机自启）
WATCHDOG_CRON="@reboot cd $WORKSPACE && python3 task_watchdog.py --daemon >> logs/watchdog.log 2>&1"
if ! crontab -l 2>/dev/null | grep -q "task_watchdog.py"; then
    (crontab -l 2>/dev/null; echo "$WATCHDOG_CRON") | crontab -
    ok "添加看门狗自启动"
fi

ok "定时任务设置完成"

# =============================================================================
# 7. 启动看门狗
# =============================================================================
log "启动看门狗守护进程..."

if pgrep -f "task_watchdog.py" > /dev/null; then
    warn "看门狗已在运行"
else
    nohup python3 task_watchdog.py --daemon > logs/watchdog.log 2>&1 &
    sleep 2
    if pgrep -f "task_watchdog.py" > /dev/null; then
        ok "看门狗已启动"
    else
        err "看门狗启动失败，请检查 logs/watchdog.log"
    fi
fi

# =============================================================================
# 8. 完成
# =============================================================================
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  ✅ 安装完成！"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "  📂 工作目录: $WORKSPACE"
echo ""
echo "  🚀 快速开始："
echo "     python3 demo.py --demo ecommerce --scenario   # 电商记忆演进"
echo "     python3 demo.py --demo 1                      # 长连接审批 Demo"
echo "     python3 demo.py --demo 2                      # 回调地址审批 Demo"
echo ""
echo "  📖 完整文档："
echo "     cat README.md"
echo "     cat ANTI_BLACKBOX.md    # 反黑箱机制说明"
echo "     cat SECURITY.md         # 安全政策"
echo ""
echo "  🛠️  常用命令："
echo "     openclaw status         # 查看 OpenClaw 状态"
echo "     openclaw gateway start  # 启动网关"
echo "     python3 task_watchdog.py --daemon  # 看门狗后台运行"
echo ""
echo "  🦐 参与贡献："
echo "     https://github.com/YuchenKuney/openclaw-memory-architecture-public"
echo "     欢迎提 Issue 和 PR，优秀建议将加入 CONTRIBUTORS.md 荣誉榜！"
echo ""
