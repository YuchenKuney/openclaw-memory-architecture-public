#!/usr/bin/env python3
"""手动触发记忆同步-18:30"""
import subprocess, os, json
from datetime import datetime

WORKSPACE = "/root/.openclaw/workspace"
CRON_DIR = f"{WORKSPACE}/cron-events"

# 写入事件
event = {
    "event": "记忆同步-18:30",
    "action": "fired",
    "message": "📝坤哥，日常记忆同步时间到！正在整理记忆碎片...",
    "timestamp": datetime.now().isoformat(),
}
name = "记忆同步-18-30手动"
filename = f"{CRON_DIR}/{name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
with open(filename, "w", encoding="utf-8") as f:
    json.dump(event, f, ensure_ascii=False)
print(f"✅ 写入: {filename}")

# 检查 clawkeeper 是否在运行
result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
if "clawkeeper.watcher" in result.stdout:
    print("✅ clawkeeper.watcher 在运行")
else:
    print("❌ clawkeeper.watcher 未运行")

# 检查 cron-events 目录
print(f"\n当前 cron-events 内容:")
for f in os.listdir(CRON_DIR):
    print(f"  {f}")
