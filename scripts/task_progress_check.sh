#!/bin/bash
# Task Progress Checker v2.0
# 解析 tasks/T-*.md (v2.0 YAML格式)
# 输出：坤哥可读格式

TASKS_DIR="/root/.openclaw/workspace/tasks"

for f in "$TASKS_DIR"/T-*.md; do
    [ -f "$f" ] || continue
    [[ "$f" == *"archive"* ]] && continue
    
    TASK_ID=$(basename "$f" .md)
    
    # 提取任务名（从第一行标题）
    NAME=$(grep "^# " "$f" | head -1 | sed 's/^# T-[0-9]*-//')
    [ -z "$NAME" ] && NAME=$(grep "^name:" "$f" | head -1 | awk '{print $2}')
    
    # 提取状态
    STATUS=$(grep "^status:" "$f" | head -1 | awk '{print $2}')
    
    # 提取 progress（computed 字段）
    PROGRESS=$(grep "^progress:" "$f" | head -1 | awk '{print $2}')
    [ -z "$PROGRESS" ] && PROGRESS="0"
    
    # 提取 updated_at
    UPDATED=$(grep "^  updated_at:" "$f" | head -1 | awk '{gsub(/"/,"",$2); print $2}')
    
    # 解析 steps
    TOTAL=$(grep -c '^\s*- id:' "$f" 2>/dev/null || echo 0)
    DONE=$(grep 'status: "done"' "$f" 2>/dev/null | wc -l)
    RUNNING=$(grep 'status: "running"' "$f" 2>/dev/null | wc -l)
    
    # 进度条（纯bash）
    PCT_INT=0
    if [ -n "$PROGRESS" ]; then
        PCT_INT=$(echo "$PROGRESS" | awk '{printf "%d", $1 * 100}')
    fi
    BAR_LEN=10
    FILLED=$((PCT_INT * BAR_LEN / 100))
    [ "$FILLED" -gt "$BAR_LEN" ] && FILLED=$BAR_LEN
    
    BAR=""
    for i in $(seq 1 $BAR_LEN); do
        if [ $i -le $FILLED ]; then
            BAR="${BAR}█"
        else
            BAR="${BAR}░"
        fi
    done
    
    # 状态 emoji
    case "$STATUS" in
        running)    ICON="🔄" ;;
        done)       ICON="✅" ;;
        error)      ICON="❌" ;;
        pending)    ICON="⏳" ;;
        *)          ICON="📋" ;;
    esac
    
    # 超时检测
    STALE=""
    if [ -n "$UPDATED" ]; then
        LAST_EPOCH=$(date -d "$UPDATED" +%s 2>/dev/null || echo 0)
        NOW_EPOCH=$(date +%s)
        [ "$LAST_EPOCH" -gt 0 ] 2>/dev/null && {
            DIFF=$((NOW_EPOCH - LAST_EPOCH))
            [ "$DIFF" -gt 900 ] && STALE=" ⚠️卡住${DIFF}秒"
        }
    fi
    
    echo "$ICON $TASK_ID: $NAME"
    echo "   [$BAR] ${PCT_INT}% | ${DONE}/${TOTAL} steps${STALE}"
    [ -n "$UPDATED" ] && echo "   更新: $UPDATED"
    echo ""
done
