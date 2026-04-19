#!/usr/bin/env python3
"""
Cron Event Writer - 定时任务触发时写事件文件，供 clawkeeper 监控
"""
import sys
import json
import os
from datetime import datetime

if len(sys.argv) < 3:
    print("Usage: cron-event-writer.py <job_name> <status> [message]")
    sys.exit(1)

job_name = sys.argv[1]
status = sys.argv[2]  # fired / running / done / error
message = sys.argv[3] if len(sys.argv) > 3 else ""

# 转换时间戳
now = datetime.now()
triggered_at = now.strftime("%Y-%m-%d %H:%M:%S")
date_stamp = now.strftime("%Y%m%d")
time_stamp = now.strftime("%H%M%S")

# 生成稳定文件名（同一分钟内重复触发不会重复）
safe_name = job_name.replace(" ", "-").replace(":", "-")
filename = f"/root/.openclaw/workspace/cron-events/{safe_name}-{date_stamp}-{time_stamp}.json"

event = {
    "job": job_name,
    "status": status,
    "triggeredAt": triggered_at,
    "message": message,
}

with open(filename, 'w', encoding='utf-8') as f:
    json.dump(event, f, ensure_ascii=False, indent=2)

print(f"Cron event written: {filename}")
