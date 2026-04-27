#!/usr/bin/env python3
"""先启动监控，再写入文件，看能否捕获"""
import subprocess, time, os, json

# 启动 clawkeeper
subprocess.run(["bash", "-c", "cd /root/.openclaw/workspace/clawkeeper && bash start.sh"], capture_output=True)
time.sleep(2)

# 写入事件文件
test_file = '/root/.openclaw/workspace/cron-events/_test_new.json'
with open(test_file, 'w') as f:
    json.dump({"event": "NEW", "action": "fired"}, f)
print(f"写入: {test_file}")

# 等待 clawkeeper 处理
time.sleep(3)

# 检查 clawkeeper 日志有没有处理记录
result = subprocess.run(["grep", "test_new", "/root/.openclaw/workspace/clawkeeper/watchdog.log"], capture_output=True, text=True)
print(f"clawkeeper日志: {result.stdout if result.stdout else '(无相关日志)'}")

# 清理
os.remove(test_file)
