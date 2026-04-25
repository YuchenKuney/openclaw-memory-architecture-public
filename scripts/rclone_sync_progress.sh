#!/bin/bash
# rclone_sync_progress.sh - 带主动推送的同步脚本
# 使用方式: ./rclone_sync_progress.sh
#
# 环境变量:
#   RCLONE_REMOTE    - rclone remote 名称（如 yuchen）
#   RCLONE_DEST      - 目标路径（如 "openclaw三层记忆架构备份/openclaw-memory"）
#   RCLONE_SOURCE     - 源路径（默认当前目录 .）
#   FEISHU_WEBHOOK   - 飞书 Webhook URL
#   EXCLUDE_PATTERN  - 排除模式（如 "memory/[0-9]*" 用双引号包裹）

set -e

REMOTE="${RCLONE_REMOTE:-yuchen}"
DEST="${RCLONE_DEST:-}"
SOURCE="${RCLONE_SOURCE:-.}"
WEBHOOK="${FEISHU_WEBHOOK:-YOUR_FEISHU_WEBHOOK_URL}"

EXCLUDES="--exclude tasks/archive/ --exclude memory/[0-9]*.md --exclude IDENTITY.md --exclude SOUL.md --exclude USER.md --exclude .openclaw/ --exclude openclaw_config/ --exclude *.log --exclude .serpapi_key"

if [ -z "$DEST" ]; then
    echo "请设置 RCLONE_DEST 环境变量"
    exit 1
fi

TASK_ID="T-SYNC-$(date +%H%M%S)"

push() {
    local msg="$1"
    local pct="${2:-}"
    local text
    if [ -n "$pct" ]; then
        text="🔄 ${TASK_ID}: ${msg} (${pct}%)"
    else
        text="🔄 ${TASK_ID}: ${msg}"
    fi
    curl -s -X POST "$WEBHOOK" \
        -H "Content-Type: application/json" \
        -d "{\"msg_type\":\"text\",\"content\":{\"text\":\"$text\"}}" \
        > /dev/null 2>&1
}

echo "=== 同步进度推送脚本 ==="
echo "Remote: $REMOTE"
echo "Dest: $DEST"
echo "Source: $SOURCE"

push "同步开始..." 0

# 检查 rclone 连接
if ! timeout 10 rclone about "$REMOTE" > /dev/null 2>&1; then
    push "❌ rclone 连接失败，请检查网络和 token" 0
    echo "rclone connection failed"
    exit 1
fi

push "正在同步，已开始处理文件..." 10

# 获取文件数量估算
TOTAL=$(rclone ls "$SOURCE" $EXCLUDES --max-depth 999 2>/dev/null | wc -l || echo 0)
push "预计 $TOTAL 个文件需要同步..." 15

# 执行同步，显示进度
rclone copy "$SOURCE" "$REMOTE:$DEST" \
    $EXCLUDES \
    --transfers 4 \
    --stats 10s \
    --stats-one-line \
    -v 2>&1 | while IFS= read -r line; do
        # 每30秒推送一次进度
        echo "[$(date '+%H:%M:%S')] $line"
        
        # 解析进度（rclone 输出示例: "Transferred:   1.234 MiB / 10.123 MiB, 12%, 1.2 MiB/s")
        if echo "$line" | grep -q "Transferred:"; then
            PCT=$(echo "$line" | grep -oP '\d+(?=%)' | tail -1)
            if [ -n "$PCT" ]; then
                echo "Progress: $PCT%"
            fi
        fi
    done

EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -eq 0 ]; then
    push "✅ 同步完成！" 100
else
    push "⚠️ 同步完成（有警告，请检查日志）" 100
fi

echo "=== 同步完成，退出码: $EXIT_CODE ==="