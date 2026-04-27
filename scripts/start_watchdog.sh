#!/bin/bash
# OpenClaw Task Watchdog 启动脚本（后台常驻）
# 用法: ./start_watchdog.sh

LOG="/root/.openclaw/workspace/memory/watchdog-daemon.log"
PIDFILE="/root/.openclaw/workspace/.watchdog.pid"

cd /root/.openclaw/workspace

# 如果已有进程在运行，先杀掉
if [ -f "$PIDFILE" ]; then
    OLD_PID=$(cat "$PIDFILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[Watchdog] 已有进程 PID=$OLD_PID，杀掉重启"
        kill "$OLD_PID" 2>/dev/null
        sleep 1
    fi
fi

# 启动看门狗（前台运行，shell 负责后台化）
exec python3 task_watchdog.py --systemd >> "$LOG" 2>&1 &
WD_PID=$!
echo "$WD_PID" > "$PIDFILE"
echo "[Watchdog] 已启动 PID=$WD_PID"
