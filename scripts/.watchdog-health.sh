#!/bin/bash
# 看门狗健康检查脚本
# 每 2 分钟 cron 运行：检查 watchdog + task_monitor 是否存活
# 如有需要，自动拉起

WATCHDOG_PID_FILE="/root/.openclaw/workspace/.watchdog.pid"
STATE_FILE="/root/.openclaw/workspace/.watchdog_state.json"
LOG="/root/.openclaw/workspace/memory/watchdog-health.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [健康检查] $1" >> "$LOG"
}

# 检查 task_monitor.py 是否存活
MONITOR_PID=$(python3 -c "import json; d=json.load(open('$STATE_FILE')); print(d.get('monitor_pid',''))" 2>/dev/null)
if [ -n "$MONITOR_PID" ] && kill -0 "$MONITOR_PID" 2>/dev/null; then
    log "task_monitor.py (PID=$MONITOR_PID) ✅ 存活"
else
    log "task_monitor.py (PID=$MONITOR_PID) ❌ 已停止，尝试拉起..."
    python3 -u /root/.openclaw/workspace/task_watchdog.py --daemon >> /root/.openclaw/workspace/memory/watchdog-daemon.log 2>&1 &
    log "watchdog 已在后台启动"
fi

# 检查 watchdog 进程是否存活（通过 PIDFile）
if [ -f "$WATCHDOG_PID_FILE" ]; then
    WD_PID=$(cat "$WATCHDOG_PID_FILE")
    if kill -0 "$WD_PID" 2>/dev/null; then
        log "watchdog (PID=$WD_PID) ✅ 存活"
    else
        log "watchdog (PID=$WD_PID) ❌ 已停止，重新拉起..."
        python3 -u /root/.openclaw/workspace/task_watchdog.py --daemon >> /root/.openclaw/workspace/memory/watchdog-daemon.log 2>&1 &
        log "watchdog 已在后台重启"
    fi
else
    log "watchdog PIDFile 不存在，重新拉起..."
    python3 -u /root/.openclaw/workspace/task_watchdog.py --daemon >> /root/.openclaw/workspace/memory/watchdog-daemon.log 2>&1 &
fi
