#!/usr/bin/env python3
"""
任务监控子 Agent

作为后台 agent 运行，持续读取 .task_state.json 并汇报进度。
由 main session 启动，任务完成后自动退出。
"""

import json
import time
import sys
import os
import urllib.request
from datetime import datetime
from pathlib import Path

STATE_FILE = Path("/root/.openclaw/workspace/.task_state.json")
WEBHOOK = "YOUR_FEISHU_WEBHOOK_URL"
CHECK_INTERVAL = 120  # 每2分钟检查一次
MAX_RUNTIME = 86400  # 24小时


def read_state():
    if not STATE_FILE.exists():
        return None
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return None


def build_bar(current, total):
    filled = round(current / total * 10)
    return "█" * filled + "░" * (10 - filled)


def send_card(state):
    task = state["task"]
    total = state["total_steps"]
    step = state.get("current_step", 0)
    step_name = state.get("step_name", "进行中")
    next_step = state.get("next_step", "")
    progress = state.get("progress", 0)
    eta = state.get("eta_seconds", 0)
    status = state.get("status", "running")
    last_updated = state.get("last_updated", "")
    
    bar = build_bar(step, total)

    if status == "done":
        color, template = "✅ 任务完成", "green"
    elif status == "error":
        color, template = "🔴 任务出错", "red"
    else:
        color, template = "🔄 进行中", "orange"

    elements = [
        {"tag": "markdown", "content": f"**🤖 当前任务**: `{task}`"},
        {"tag": "markdown", "content": f"**{color}**: {bar} **{progress}%**"},
        {"tag": "markdown", "content": f"**📍 Step {step}/{total}**: `{step_name}`"},
    ]
    if next_step:
        elements.append({"tag": "markdown", "content": f"**➡️  下一步**: `{next_step}`"})
    if eta > 0:
        t = f"约 {eta} 秒" if eta < 60 else f"约 {eta//60} 分钟"
        elements.append({"tag": "markdown", "content": f"**⏱️  预计**: {t}"})
    elements.extend([
        {"tag": "markdown", "content": f"**🕐 最后更新**: `{last_updated}`"},
        {"tag": "hr"},
        {"tag": "markdown", "content": "_🤖 Agent 实时监控中，每2分钟汇报一次_"}
    ])
    if status == "done":
        msg = state.get("completion_message", "")
        if msg:
            elements.insert(2, {"tag": "markdown", "content": f"**📝 总结**: {msg}"})
    elif status == "error":
        elements.insert(2, {"tag": "markdown", "content": f"**❌ 错误**: `{state.get('error_message','')}`"})

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": f"{color} | {task}"}, "template": template},
            "elements": elements
        }
    }

    try:
        data = json.dumps(card, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(WEBHOOK, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            return result.get("StatusCode") or result.get("code") == 0
    except Exception:
        return False


def main():
    print(f"[task-monitor-agent] 启动监控 agent（每{CHECK_INTERVAL}秒检查一次）")
    print(f"[task-monitor-agent] 最大运行时长: {MAX_RUNTIME//60} 分钟")
    
    start_time = time.time()
    last_status = None  # 避免重复发送

    while time.time() - start_time < MAX_RUNTIME:
        state = read_state()

        if not state:
            # 无任务，等待一下再检查
            time.sleep(CHECK_INTERVAL)
            continue

        status = state.get("status", "running")

        # done/error 只发一次然后退出
        if status in ("done", "error"):
            send_card(state)
            STATE_FILE.unlink(missing_ok=True)
            print(f"[task-monitor-agent] 任务{status}，汇报后退出")
            break

        # running 状态定期汇报（每2分钟）
        if status == "running" and state != last_status:
            ok = send_card(state)
            if ok:
                print(f"[task-monitor-agent] 进度汇报: {state['task']} {state.get('progress',0)}%")
                last_status = state.copy() if state else None

        time.sleep(CHECK_INTERVAL)

    print(f"[task-monitor-agent] 监控结束（运行时长: {int(time.time()-start_time)}秒）")


if __name__ == "__main__":
    main()
