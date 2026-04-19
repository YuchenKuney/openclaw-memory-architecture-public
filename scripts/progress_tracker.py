#!/usr/bin/env python3
"""
Progress Tracker - 任务进度追踪器
用法:
    python3 progress_tracker.py start <job_name> [message]   # 开始任务
    python3 progress_tracker.py <job_id> <progress> <step> [message]  # 更新进度
    python3 progress_tracker.py done <job_id> [message]     # 完成
    python3 progress_tracker.py error <job_id> <message>   # 错误
    python3 progress_tracker.py list                        # 查看所有任务

进度文件路径: tasks/progress/{job_id}.json
"""
import sys
import json
import os
from datetime import datetime
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
PROGRESS_DIR = WORKSPACE / "tasks" / "progress"
PROGRESS_DIR.mkdir(parents=True, exist_ok=True)

def get_job_file(job_id):
    return PROGRESS_DIR / f"{job_id}.json"

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def write_progress(job_id, data):
    """写入进度文件"""
    job_file = get_job_file(job_id)
    with open(job_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return job_file

def start_job(job_name, message=""):
    """开始一个新任务"""
    job_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}"
    data = {
        "jobId": job_id,
        "jobName": job_name,
        "status": "running",
        "progress": 0,
        "step": "开始执行",
        "message": message,
        "startedAt": now_str(),
        "updatedAt": now_str(),
        "steps": [
            {"step": 0, "name": "开始执行", "progress": 0, "timestamp": now_str()}
        ]
    }
    write_progress(job_id, data)
    print(f"✅ 任务已创建: {job_id} ({job_name})")
    return job_id

def update_job(job_id, progress, step, message=""):
    """更新任务进度"""
    job_file = get_job_file(job_id)
    if not job_file.exists():
        print(f"❌ 任务不存在: {job_id}")
        return

    with open(job_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    data["progress"] = progress
    data["step"] = step
    data["message"] = message
    data["updatedAt"] = now_str()
    data["steps"].append({
        "step": progress,
        "name": step,
        "timestamp": now_str()
    })

    write_progress(job_id, data)
    print(f"📝 进度更新: [{progress}%] {step}")

def complete_job(job_id, message=""):
    """完成任务"""
    job_file = get_job_file(job_id)
    if not job_file.exists():
        print(f"❌ 任务不存在: {job_id}")
        return

    with open(job_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    data["status"] = "done"
    data["progress"] = 100
    data["step"] = "已完成"
    data["message"] = message
    data["updatedAt"] = now_str()

    write_progress(job_id, data)
    print(f"✅ 任务完成: {job_id}")

def error_job(job_id, message=""):
    """标记任务错误"""
    job_file = get_job_file(job_id)
    if not job_file.exists():
        print(f"❌ 任务不存在: {job_id}")
        return

    with open(job_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    data["status"] = "error"
    data["message"] = message
    data["updatedAt"] = now_str()

    write_progress(job_id, data)
    print(f"🔴 任务异常: {job_id} - {message}")

def list_jobs():
    """列出所有活跃任务"""
    jobs = []
    for f in PROGRESS_DIR.glob("*.json"):
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
                if data.get("status") in ("running",):
                    jobs.append(data)
        except:
            pass
    if not jobs:
        print("无活跃任务")
    else:
        for j in jobs:
            print(f"  [{j['progress']:3d}%] {j['jobName']} | {j['step']} | {j['jobId']}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "start":
        if len(sys.argv) < 3:
            print("用法: progress_tracker.py start <job_name> [message]")
            sys.exit(1)
        job_name = sys.argv[2]
        message = sys.argv[3] if len(sys.argv) > 3 else ""
        start_job(job_name, message)

    elif cmd == "list":
        list_jobs()

    elif cmd == "done":
        if len(sys.argv) < 3:
            print("用法: progress_tracker.py done <job_id> [message]")
            sys.exit(1)
        job_id = sys.argv[2]
        message = sys.argv[3] if len(sys.argv) > 3 else ""
        complete_job(job_id, message)

    elif cmd == "error":
        if len(sys.argv) < 3:
            print("用法: progress_tracker.py error <job_id> <message>")
            sys.exit(1)
        job_id = sys.argv[2]
        message = sys.argv[3] if len(sys.argv) > 3 else ""
        error_job(job_id, message)

    elif cmd in ("0", "10", "20", "30", "40", "50", "60", "70", "80", "90", "100"):
        # 当作 progress 参数
        job_id = cmd
        if len(sys.argv) < 4:
            print("用法: progress_tracker.py <job_id> <progress> <step> [message]")
            sys.exit(1)
        try:
            progress = int(sys.argv[2])
        except ValueError:
            job_id = sys.argv[1]
            progress = int(sys.argv[2])
        step = sys.argv[3] if len(sys.argv) > 3 else ""
        message = sys.argv[4] if len(sys.argv) > 4 else ""
        update_job(job_id, progress, step, message)

    else:
        # 第一个参数是 job_id
        job_id = cmd
        if len(sys.argv) < 3:
            print(__doc__)
            sys.exit(1)
        try:
            progress = int(sys.argv[2])
        except ValueError:
            print(f"未知命令: {cmd}")
            sys.exit(1)
        step = sys.argv[3] if len(sys.argv) > 3 else ""
        message = sys.argv[4] if len(sys.argv) > 4 else ""
        update_job(job_id, progress, step, message)
