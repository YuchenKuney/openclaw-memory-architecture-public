#!/bin/bash
WORKSPACE="$(dirname "$(dirname "$(readlink -f "$0")")")"
cd "$WORKSPACE/clawkeeper"
export WORKSPACE
export PYTHONPATH="$WORKSPACE:$PYTHONPATH"
export PYTHONUNBUFFERED=1
LOG_FILE="/root/.openclaw/workspace/clawkeeper/watchdog.log"
echo "🛡️ Clawkeeper 启动中..."
python3 -u -m clawkeeper.watcher >> "$LOG_FILE" 2>&1 &
PID=$!
echo $PID > clawkeeper.pid
echo "✅ Clawkeeper 已启动 (PID: $PID)"
