#!/bin/bash
# 任务进度主动推送
# 使用方式: ./task_push.sh "T-001" "S1" "done" "描述" "50"
#
# 环境变量:
#   FEISHU_WEBHOOK - 飞书 Webhook URL（优先读取）
#   PUSH_TASK_ID   - 任务ID前缀，默认 T-YYYYMMDD-HHMMSS

# 坤哥飞书群 Webhook（已配置）
WEBHOOK="${FEISHU_WEBHOOK:-https://open.feishu.cn/open-apis/bot/v2/hook/375a8be1-9e3e-4758-a78b-e775fd4d32a1}"

TASK_ID="${1:-}"
STEP_ID="${2:-}"
STATUS="${3:-}"
MSG="${4:-}"
PROGRESS="${5:-}"

ICON=""
case "$STATUS" in
    running)   ICON="🔄" ;;
    done)      ICON="✅" ;;
    error)     ICON="❌" ;;
    waiting_*) ICON="⏳" ;;
    pending)   ICON="⏳" ;;
    *)         ICON="📋" ;;
esac

if [ -n "$PROGRESS" ]; then
    TEXT="$ICON $TASK_ID $STEP_ID $STATUS (${PROGRESS}%)\n$MSG"
else
    TEXT="$ICON $TASK_ID $STEP_ID $STATUS\n$MSG"
fi

curl -s -X POST "$WEBHOOK" \
    -H "Content-Type: application/json" \
    -d "{\"msg_type\":\"text\",\"content\":{\"text\":\"$TEXT\"}}" \
    > /dev/null 2>&1

echo "[$(date '+%H:%M:%S')] Pushed: $TASK_ID $STEP_ID $STATUS"
