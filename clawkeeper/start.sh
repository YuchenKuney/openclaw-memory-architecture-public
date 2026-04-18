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
