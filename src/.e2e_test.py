#!/usr/bin/env python3
"""端到端整合验证 - 方案A完整流程"""
import subprocess, time, sys, re
sys.path.insert(0, '/root/.openclaw/workspace')

tracker = "/root/.openclaw/workspace/scripts/progress_tracker.py"
log_file = "/root/.openclaw/workspace/clawkeeper/watchdog.log"

def run_tracker(*args):
    result = subprocess.run(["python3", tracker] + list(args),
                          capture_output=True, text=True)
    output = result.stdout + result.stderr
    print(output.strip())
    return output

# Step 1: 启动任务，捕获返回的 JOB_ID
print("【Step 1】启动任务")
output = run_tracker("start", "T-E2E", "深度整合验证-代码审计")
# 从输出中解析 JOB_ID=...
job_id = None
for line in output.split("\n"):
    if line.startswith("JOB_ID="):
        job_id = line.split("=")[1].strip()
        break

if not job_id:
    print("❌ 无法获取 JOB_ID，退出")
    sys.exit(1)
print(f"→ 捕获到 JOB_ID: {job_id}")
time.sleep(2)

# Step 2-4: 更新进度
for pct, step_desc in [
    (25, "Step 1/4 - 读取源码结构"),
    (50, "Step 2/4 - 检查敏感操作模式"),
    (75, "Step 3/4 - 分析 import 依赖链"),
]:
    print(f"【进度 {pct}%】{step_desc}")
    run_tracker(job_id, str(pct), step_desc)
    time.sleep(2)

# Step 5: 完成
print("【完成】")
run_tracker("done", job_id, "整合验证完成")
time.sleep(3)

# 检查日志
print("【飞书通知日志】")
log_lines = open(log_file).readlines()
notify_lines = [l.strip() for l in log_lines if "群聊进度通知" in l or "Notifier" in l]
for l in notify_lines[-10:]:
    print(l)

print(f"【验证】共检测到 {len(notify_lines)} 条通知")
if len(notify_lines) >= 3:
    print("✅ 方案A端到端整合验证通过")
else:
    print("⚠️ 通知数量偏少，请检查飞书群")
