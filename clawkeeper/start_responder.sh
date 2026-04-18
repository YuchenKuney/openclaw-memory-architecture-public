#!/bin/bash
# start_responder.sh - 启动 Clawkeeper Responder 后台服务
# 功能：监听飞书消息，自动处理「允许/拒绝」指令

WORKSPACE="/root/.openclaw/workspace"
LOG_FILE="$WORKSPACE/clawkeeper/logs/responder.log"
PID_FILE="$WORKSPACE/clawkeeper/responder.pid"

mkdir -p "$(dirname $LOG_FILE)"

# 检查是否已运行
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Responder 已在运行 (PID: $PID)"
        exit 0
    fi
fi

# 启动
echo "启动 Clawkeeper Responder..."
cd "$WORKSPACE/clawkeeper"

nohup python3 -c "
import sys
sys.path.insert(0, '.')
import time
import os
os.environ['WORKSPACE'] = '$WORKSPACE'

from responder import CommandResponder, FeishuMessageListener
from detector import RiskDetector
from notifier import FeishuNotifier

detector = RiskDetector()
notifier = FeishuNotifier()
interceptor = Interceptor(detector, notifier)

# 动态导入避免循环依赖
from interceptor import Interceptor
interceptor = Interceptor(detector, notifier)
responder = CommandResponder(interceptor, notifier)
listener = FeishuMessageListener(responder)

print('Clawkeeper Responder 启动成功')
while True:
    try:
        listener.poll_messages()
    except Exception as e:
        print(f'Responder 异常: {e}')
    time.sleep(5)
" >> "$LOG_FILE" 2>&1 &

PID=$!
echo $PID > "$PID_FILE"
echo "Responder 已启动 (PID: $PID)"
