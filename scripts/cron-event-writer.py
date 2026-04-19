#!/usr/bin/env python3
"""
Cron Event Writer - 定时任务触发时写事件文件，供 clawkeeper 监控
支持进度追踪：python3 cron-event-writer.py <job_name> <status> [message] [progress]

用法示例:
    python3 cron-event-writer.py "记忆同步" fired "开始执行"
    python3 cron-event-writer.py "记忆同步" running "读取memory文件" 30
    python3 cron-event-writer.py "记忆同步" done "同步完成" 100
"""
import sys
import json
import os
from datetime import datetime

if len(sys.argv) < 3:
    print("Usage: cron-event-writer.py <job_name> <status> [message] [progress]")
    print("  status: fired/running/done/error")
    print("  progress: 0-100 (可选)")
    sys.exit(1)

job_name = sys.argv[1]
status = sys.argv[2]
message = sys.argv[3] if len(sys.argv) > 3 else ""
progress = int(sys.argv[4]) if len(sys.argv) > 4 else None

now = datetime.now()
triggered_at = now.strftime("%Y-%m-%d %H:%M:%S")
date_stamp = now.strftime("%Y%m%d")
time_stamp = now.strftime("%H%M%S")

safe_name = job_name.replace(" ", "-").replace(":", "-")
filename = f"/root/.openclaw/workspace/cron-events/{safe_name}-{date_stamp}-{time_stamp}.json"

event = {
    "job": job_name,
    "status": status,
    "triggeredAt": triggered_at,
    "message": message,
}
if progress is not None:
    event["progress"] = progress

with open(filename, 'w', encoding='utf-8') as f:
    json.dump(event, f, ensure_ascii=False, indent=2)

print(f"Cron event written: {filename}")
