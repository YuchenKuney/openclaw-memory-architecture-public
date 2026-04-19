#!/bin/bash
# sync_memory.sh - 记忆同步脚本
# 功能：执行每日记忆提纯 + Git备份 + 推送通知
# 触发：每天 18:30 by cron

WORKSPACE="/root/.openclaw/workspace"
LOG_FILE="/root/.openclaw/workspace/.sync_log"

# 飞书 Webhook - 从环境变量读取（不硬编码在脚本中）
WEBHOOK="${FEISHU_WEBHOOK:-}"

echo "[$(date '+%Y-%m-%d %H:%M')] === 记忆同步开始 ===" >> "$LOG_FILE"

# Step 1: 执行每日记忆提纯（画像检测 + 日志蒸馏）
cd "$WORKSPACE"
python3 scripts/memory_scheduler.py --purify 2>&1 | tee -a "$LOG_FILE"

# Step 2: Git 自动提交（如果有变化）
cd "$WORKSPACE"
if [[ $(git status --porcelain) ]]; then
    git add -A
    git commit -m "auto: daily memory sync $(date '+%Y-%m-%d %H:%M')" 2>&1 | tee -a "$LOG_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M')] Git 已提交" >> "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M')] 无变化，跳过 Git 提交" >> "$LOG_FILE"
fi

# Step 3: 推送到 GitHub（使用 GITHUB_TOKEN 环境变量）
git push private main 2>&1 | tee -a "$LOG_FILE"

echo "[$(date '+%Y-%m-%d %H:%M')] === 记忆同步完成 ===" >> "$LOG_FILE"

# 飞书通知（只有配置了 WEBHOOK 时才发送）
if [[ -n "$WEBHOOK" ]]; then
    curl -s -X POST "$WEBHOOK" \
      -H "Content-Type: application/json" \
      -d '{"msg_type":"text","content":{"text":"🔄 记忆同步完成"}}' > /dev/null 2>&1 || true
fi

exit 0
