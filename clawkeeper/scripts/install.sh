#!/bin/bash
# Clawkeeper 安装脚本
# 安装 inotify-tools + 配置 cron 启动 + 安装 git hooks

set -e

WORKSPACE="${WORKSPACE:-/root/.openclaw/workspace}"
CLAWKEEPER_DIR="$WORKSPACE/clawkeeper"
LOG="$CLAWKEEPER_DIR/install.log"

log() {
    echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG"
}

log "🚀 开始安装 Clawkeeper V8..."

# 1. 检查 inotify-tools
log "📦 检查 inotify-tools..."
if command -v inotifywait &> /dev/null; then
    log "  ✅ inotifywait 已安装"
else
    log "  📥 安装 inotify-tools..."
    apt-get update -qq && apt-get install -y inotify-tools -qq 2>&1 | tail -3
    log "  ✅ inotify-tools 安装完成"
fi

# 2. 检查 Python 依赖
log "📦 检查 Python 依赖..."
python3 -c "import inotify.adapters" 2>/dev/null && log "  ✅ Python inotify 可用" || log "  ⚠️ Python inotify 不可用，将使用轮询模式"

# 3. 创建目录
log "📁 创建目录..."
mkdir -p "$CLAWKEEPER_DIR/reports"
mkdir -p "$CLAWKEEPER_DIR/logs"
touch "$CLAWKEEPER_DIR/audit.log"
touch "$CLAWKEEPER_DIR/config.json"
log "  ✅ 目录创建完成"

# 4. 安装 git hooks
log "🔗 安装 Git Hooks..."
if [ -f "$WORKSPACE/.git/hooks/pre-push" ]; then
    log "  ⚠️ pre-push hook 已存在，备份后替换"
    cp "$WORKSPACE/.git/hooks/pre-push" "$WORKSPACE/.git/hooks/pre-push.bak.$(date +%s)"
fi

cat > "$WORKSPACE/.git/hooks/pre-push" << 'HOOK'
#!/bin/bash
# Clawkeeper Git Hook - pre-push
WORKSPACE="$(dirname "$(dirname "$(readlink -f "$0")")")"
AUDIT="$WORKSPACE/clawkeeper/audit.log"

# 检查推送到公共仓库
remote_url=$(git remote get-url --push origin 2>/dev/null || echo "")

if echo "$remote_url" | grep -q "openclaw-memory-architecture-public"; then
    echo "⚠️  Clawkeeper: 检测到推送到公共仓库..."
    echo "$(date '+%Y-%m-%d %H:%M:%S') WARN: 推送到公共仓库: $remote_url" >> "$AUDIT"
    echo "   请确保已完成脱敏检查！"
fi

exit 0
HOOK

chmod +x "$WORKSPACE/.git/hooks/pre-push"
log "  ✅ Git Hooks 安装完成"

# 5. 创建启动脚本
log "🚀 创建启动脚本..."
cat > "$CLAWKEEPER_DIR/start.sh" << 'START'
#!/bin/bash
# Clawkeeper 启动脚本
WORKSPACE="$(dirname "$(dirname "$(readlink -f "$0")")")"
cd "$WORKSPACE/clawkeeper"

export WORKSPACE
export PYTHONPATH="$WORKSPACE:$PYTHONPATH"

echo "🛡️ Clawkeeper 启动中..."
python3 -m clawkeeper.watcher &
echo $! > clawkeeper.pid
echo "✅ Clawkeeper 已启动 (PID: $(cat clawkeeper.pid))"
START

chmod +x "$CLAWKEEPER_DIR/start.sh"

# 6. 创建 systemd 服务（可选）
if command -v systemctl &> /dev/null; then
    log "⚙️ 创建 systemd 服务..."
    cat > /etc/systemd/system/clawkeeper.service << 'SERVICE'
[Unit]
Description=Clawkeeper - AI Behavior Monitor
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/.openclaw/workspace
ExecStart=/root/.openclaw/workspace/clawkeeper/start.sh
Restart=on-failure

[Install]
WantedBy=multi-user.target
SERVICE

    systemctl daemon-reload 2>/dev/null || true
    log "  ✅ systemd 服务已创建（可选，启动: systemctl enable clawkeeper）"
fi

# 7. 验证安装
log "🔍 验证安装..."
python3 -c "
import sys
sys.path.insert(0, '$CLAWKEEPER_DIR')
from watcher import ClawWatcher
from detector import RiskDetector
from notifier import FeishuNotifier
from auditor import Auditor
print('  ✅ 所有模块导入正常')
" 2>&1 | tee -a "$LOG"

log ""
log "========================================="
log "✅ Clawkeeper V8 安装完成！"
log "========================================="
log ""
log "下一步："
log "  1. 启动监控: bash $CLAWKEEPER_DIR/start.sh"
log "  2. 查看状态: python3 -m clawkeeper.config"
log "  3. 启用开机自启: systemctl enable clawkeeper"
log ""
