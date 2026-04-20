#!/usr/bin/env python3
"""
Progress Tracker - 任务进度追踪器（反黑箱增强版）

每次推进告诉坤哥：做了什么、怎么做、预计多久

用法:
    python3 progress_tracker.py start <job_name> [--how 怎么做] [--steps 总步骤数] [message]
    python3 progress_tracker.py <job_id> <progress> <step> [--how 怎么做] [--eta 秒]
    python3 progress_tracker.py done <job_id> [message]
    python3 progress_tracker.py error <job_id> <message>
    python3 progress_tracker.py list
"""
import sys
import json
import re
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


def now_ts():
    return datetime.now().timestamp()


def write_progress(job_id, data):
    job_file = get_job_file(job_id)
    with open(job_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return job_file


def sanitize_job_id(name):
    s = re.sub(r'[^\w\u4e00-\u9fff-]', '_', name)
    s = re.sub(r'_+', '_', s).strip('_')
    return s or "unnamed_task"


def calc_eta(started_ts: float, progress: float) -> int:
    """根据已用时间和进度计算剩余 ETA（秒）"""
    if progress <= 0 or progress >= 100:
        return 0
    elapsed = now_ts() - started_ts
    total_estimate = elapsed / (progress / 100.0)
    remaining = total_estimate - elapsed
    return max(0, int(remaining))


def start_job(job_name, message="", how="", total_steps=1):
    safe_id = sanitize_job_id(job_name)
    job_id = f"{safe_id}_{datetime.now().strftime('%H%M%S')}"
    started_ts = now_ts()
    data = {
        "jobId": job_id,
        "name": job_name,
        "status": "running",
        "progress": 0,
        "step": "开始执行",
        "how": how,           # 怎么做
        "totalSteps": total_steps,
        "eta_seconds": 0,
        "startedAt": now_str(),
        "startedTs": started_ts,
        "updatedAt": now_str(),
        "steps": [{
            "step": 0,
            "name": "开始执行",
            "how": how,
            "timestamp": now_str()
        }]
    }
    write_progress(job_id, data)
    print(f"✅ 任务已创建: {job_id} | {job_name}")
    print(f"JOB_ID={job_id}")
    return job_id


def update_job(job_id, progress, step, message="", how="", eta_seconds=None):
    job_file = get_job_file(job_id)
    if not job_file.exists():
        print(f"❌ 任务不存在: {job_id}")
        return

    with open(job_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    started_ts = data.get("startedTs", now_ts())
    if eta_seconds is None:
        eta_seconds = calc_eta(started_ts, progress)

    data["progress"] = progress
    data["step"] = step
    data["how"] = how or data.get("how", "")
    data["eta_seconds"] = eta_seconds
    data["updatedAt"] = now_str()
    data["steps"].append({
        "step": progress,
        "name": step,
        "how": how or "",
        "timestamp": now_str()
    })

    write_progress(job_id, data)
    print(f"📝 进度更新: [{progress}%] {step} | ETA: {eta_seconds}s | how: {how or '同上'}")


def complete_job(job_id, message=""):
    job_file = get_job_file(job_id)
    if not job_file.exists():
        print(f"❌ 任务不存在: {job_id}")
        return

    with open(job_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    data["status"] = "done"
    data["progress"] = 100
    data["step"] = "已完成"
    data["eta_seconds"] = 0
    data["updatedAt"] = now_str()

    write_progress(job_id, data)
    print(f"✅ 任务完成: {job_id}")


def error_job(job_id, message=""):
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
    jobs = []
    for pf in PROGRESS_DIR.glob("*.json"):
        try:
            data = json.loads(pf.read_text())
            if data.get("status") in ("running",):
                jobs.append(data)
        except:
            pass
    if not jobs:
        print("无活跃任务")
    else:
        for j in jobs:
            name = j.get('name', j.get('jobId', '?'))
            prog = j.get('progress', 0)
            step = j.get('step', '')
            how = j.get('how', '')
            eta = j.get('eta_seconds', 0)
            print(f"  [{prog:3d}%] {name}")
            print(f"         📍 {step}")
            if how:
                print(f"         🔧 {how}")
            if eta > 0:
                print(f"         ⏱️  约 {eta}s 后完成")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    # 解析 --how / --steps / --eta 参数
    def get_flag(flags):
        for f in flags:
            if f in sys.argv:
                idx = sys.argv.index(f)
                val = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
                sys.argv.pop(idx)
                if idx < len(sys.argv) and not sys.argv[idx].startswith("-"):
                    val = sys.argv.pop(idx)
                else:
                    val = ""
                return val
        return ""

    how = get_flag(["--how", "-h"])
    total_steps_str = get_flag(["--steps", "-n"])
    eta_str = get_flag(["--eta", "-e"])
    total_steps = int(total_steps_str) if total_steps_str.isdigit() else 1
    eta = int(eta_str) if eta_str.isdigit() else None

    if cmd == "start":
        if len(sys.argv) < 3:
            print(__doc__); sys.exit(1)
        job_name = sys.argv[2]
        message = sys.argv[3] if len(sys.argv) > 3 else ""
        start_job(job_name, message, how=how, total_steps=total_steps)

    elif cmd == "list":
        list_jobs()

    elif cmd == "done":
        if len(sys.argv) < 3:
            print(__doc__); sys.exit(1)
        complete_job(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")

    elif cmd == "error":
        if len(sys.argv) < 3:
            print(__doc__); sys.exit(1)
        error_job(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")

    elif cmd in ("0", "10", "20", "30", "40", "50", "60", "70", "80", "90", "100"):
        if len(sys.argv) < 4:
            print(__doc__); sys.exit(1)
        try:
            progress = int(sys.argv[2])
        except ValueError:
            progress = int(sys.argv[1])
        step = sys.argv[3] if len(sys.argv) > 3 else ""
        message = sys.argv[4] if len(sys.argv) > 4 else ""
        job_id = sys.argv[2] if cmd in ("10","20","30","40","50","60","70","80","90","100") else sys.argv[1]
        update_job(job_id, progress, step, message, how=how, eta_seconds=eta)

    else:
        job_id = cmd
        if len(sys.argv) < 3:
            print(__doc__); sys.exit(1)
        try:
            progress = int(sys.argv[2])
        except ValueError:
            print(f"未知命令: {cmd}"); sys.exit(1)
        step = sys.argv[3] if len(sys.argv) > 3 else ""
        message = sys.argv[4] if len(sys.argv) > 4 else ""
        update_job(job_id, progress, step, message, how=how, eta_seconds=eta)
