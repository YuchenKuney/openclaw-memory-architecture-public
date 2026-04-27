#!/bin/bash
# 简单循环守护：watchdog 进程挂了就自动拉起
LOG="/root/.openclaw/workspace/memory/watchdog-daemon.log"
PIDFILE="/root/.openclaw/workspace/.watchdog.pid"
SCRIPT="/root/.openclaw/workspace/task_watchdog.py"

while true; do
    if [ -f "$PIDFILE" ]; then
        OLD_PID=$(cat "$PIDFILE" 2>/dev/null)
        if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
            # 进程还在跑，sleep 之后继续检查
            sleep 30
            continue
        fi
    fi
    
    # 启动看门狗
    echo "[$(date)] 启动看门狗..." >> "$LOG"
    python3 "$SCRIPT" --once >> "$LOG" 2>&1 &
    WD_PID=$!
    echo "$WD_PID" > "$PIDFILE"
    echo "[$(date)] 看门狗已启动 PID=$WD_PID" >> "$LOG"
    
    # 等待5秒后检查是否还在
    sleep 5
    if ! kill -0 "$WD_PID" 2>/dev/null; then
        echo "[$(date)] 看门狗立即退出，重试" >> "$LOG"
    else
        echo "[$(date)] 看门狗运行正常 PID=$WD_PID" >> "$LOG"
    fi
done
