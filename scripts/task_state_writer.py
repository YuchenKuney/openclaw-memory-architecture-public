#!/usr/bin/env python3
"""
任务状态写入器

用法：
    python3 task_state_writer.py start "Shopee 市场调研" 4
    python3 task_state_writer.py step 1 "分析市场数据" "下一步：整理报告" 30
    python3 task_state_writer.py done "调研完成"
    python3 task_state_writer.py clear

状态文件：/root/.openclaw/workspace/.task_state.json
"""

import sys
import json
import os
from datetime import datetime
from pathlib import Path

STATE_FILE = Path("/root/.openclaw/workspace/.task_state.json")


def read_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {}
    return {}


def write_state(data):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_start(task_name: str, total_steps: int = 1, task_desc: str = ""):
    state = {
        "task": task_name,
        "total_steps": total_steps,
        "current_step": 0,
        "step_name": "开始执行",
        "next_step": "",
        "eta_seconds": 0,
        "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "running",
    }
    write_state(state)
    print(f"✅ 任务开始: {task_name} ({total_steps} 步)")
    print(f"STATE_FILE={STATE_FILE}")

    # 启动后台监控 agent（subprocess，生命周期独立于父进程）
    import subprocess, os
    monitor_script = "/root/.openclaw/workspace/scripts/task_monitor_agent.py"
    if os.path.exists(monitor_script):
        # 启动后台进程（nohup + 重定向输出）
        with open("/dev/null", "w") as devnull:
            subprocess.Popen(
                ["python3", monitor_script],
                stdout=devnull, stderr=devnull,
                start_new_session=True
            )
        print("✅ 后台监控 agent 已启动（每2分钟汇报一次）")
    else:
        print("⚠️ task_monitor_agent.py 不存在，跳过监控启动")


def cmd_step(step_num: int, step_name: str, next_step: str = "", eta_seconds: int = 0):
    state = read_state()
    if not state:
        print("⚠️ 没有活跃任务")
        return

    progress = round(step_num / state["total_steps"] * 100)
    state["current_step"] = step_num
    state["step_name"] = step_name
    state["next_step"] = next_step
    state["eta_seconds"] = eta_seconds
    state["progress"] = progress
    state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    write_state(state)
    print(f"✅ Step {step_num}/{state['total_steps']}: {step_name} (进度 {progress}%)")


def cmd_done(message: str = ""):
    state = read_state()
    if not state:
        print("⚠️ 没有活跃任务")
        return

    state["status"] = "done"
    state["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state["completion_message"] = message
    state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    write_state(state)
    print(f"✅ 任务完成: {state['task']} | {message}")


def cmd_error(error_message: str):
    state = read_state()
    if not state:
        print("⚠️ 没有活跃任务")
        return

    state["status"] = "error"
    state["error_message"] = error_message
    state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    write_state(state)
    print(f"🔴 任务出错: {error_message}")


def cmd_clear():
    if STATE_FILE.exists():
        STATE_FILE.unlink()
        print("✅ 状态已清除")
    else:
        print("没有状态文件")


def cmd_show():
    state = read_state()
    if not state:
        print("没有活跃任务")
        return
    print(json.dumps(state, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "start":
        if len(sys.argv) < 3:
            print("用法: start <任务名> [总步骤数] [描述]")
            sys.exit(1)
        task_name = sys.argv[2]
        total = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        desc = sys.argv[4] if len(sys.argv) > 4 else ""
        cmd_start(task_name, total, desc)

    elif cmd == "step":
        if len(sys.argv) < 4:
            print("用法: step <当前步骤> <步骤名> [下一步] [ETA秒]")
            sys.exit(1)
        step_num = int(sys.argv[2])
        step_name = sys.argv[3]
        next_step = sys.argv[4] if len(sys.argv) > 4 else ""
        eta = int(sys.argv[5]) if len(sys.argv) > 5 else 0
        cmd_step(step_num, step_name, next_step, eta)

    elif cmd == "done":
        msg = sys.argv[2] if len(sys.argv) > 2 else ""
        cmd_done(msg)

    elif cmd == "error":
        msg = sys.argv[2] if len(sys.argv) > 2 else "未知错误"
        cmd_error(msg)

    elif cmd == "clear":
        cmd_clear()

    elif cmd == "show":
        cmd_show()

    else:
        print(f"未知命令: {cmd}")
        print(__doc__)
        sys.exit(1)
