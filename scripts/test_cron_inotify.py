#!/usr/bin/env python3
"""手动测试：写入事件文件 + 检查 clawkeeper 是否响应"""
import os, json
from datetime import datetime

CRON_DIR = "/root/.openclaw/workspace/cron-events"
name = f"测试cron链-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
event = {
    "event": name,
    "action": "fired",
    "message": "🐟 这是一条测试消息",
    "timestamp": datetime.now().isoformat(),
}
filename = f"{CRON_DIR}/{name}.json"
with open(filename, "w", encoding="utf-8") as f:
    json.dump(event, f, ensure_ascii=False)
print(f"✅ 写入: {filename}")

# 检查文件是否在目录里
print(f"\n当前 cron-events 内容:")
for f in sorted(os.listdir(CRON_DIR)):
    print(f"  {f}")
