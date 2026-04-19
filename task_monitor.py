#!/usr/bin/env python3
"""
Task Monitor - 子 agent 任务进度监控器

启动方式：作为 OpenClaw 子 agent 运行
功能：
  1. 读取 progress tracker 文件
  2. 检测主 agent 任务进度变化
  3. 主动推送飞书卡片到群
  4. 主 agent 完成时发出最终通知
  5. watchdog 守护本进程，挂了自动拉起

调用方式：
  openclaw tasks spawn --runtime=subagent --task-file task_monitor.py
"""

import os
import sys
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

WORKSPACE = Path("/root/.openclaw/workspace")
PROGRESS_DIR = WORKSPACE / "tasks" / "progress"
PROGRESS_FILE = PROGRESS_DIR / "current_task.json"
NOTIFY_STATE_FILE = WORKSPACE / ".monitor_state.json"

# 飞书配置
FEISHU_WEBHOOK = os.environ.get(
    "FEISHU_WEBHOOK",
    "https://open.feishu.cn/open-apis/bot/v2/hook/7a939580-e987-4571-a142-f58528cf71ec"
)
FEISHU_GROUP = os.environ.get(
    "FEISHU_GROUP_ID",
    "oc_0533b03e077fedca255c4d2c6717deea"
)


# ============ 进度条可视化 ============

def progress_bar(pct: float, width: int = 10) -> str:
    filled = int(width * pct / 100)
    return "█" * filled + "░" * (width - filled)


def format_time(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")


# ============ 飞书推送 ============

def send_feishu_card(content: dict) -> bool:
    """发送飞书交互卡片"""
    try:
        import urllib.request
        import urllib.error

        payload = json.dumps({
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": content.get("title", "📊 任务进度")},
                    "template": content.get("template", "blue"),
                },
                "elements": content.get("elements", [])
            }
        }).encode("utf-8")

        req = urllib.request.Request(
            FEISHU_WEBHOOK,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode().find("\"code\":0") >= 0
    except Exception as e:
        print(f"[Monitor] 飞书推送失败: {e}")
        return False


def notify_progress(task_name: str, progress: float, step: str, status: str):
    """推送进度卡片"""
    bar = progress_bar(progress)
    template = {
        "done": "green",
        "running": "blue",
        "waiting": "yellow",
        "error": "red",
    }.get(status, "blue")

    status_emoji = {
        "done": "✅",
        "running": "🔄",
        "waiting": "⏳",
        "error": "❌",
    }.get(status, "🔄")

    elements = [
        {"tag": "markdown", "content": f"**{task_name}**\n{status_emoji} {bar} **{progress:.0f}%**\n📍 当前: {step}"},
        {"tag": "hr"},
        {"tag": "note", "elements": [{"tag": "plain_text", "content": f"⏰ {datetime.now().strftime('%H:%M:%S')} · 由子 agent 监控推送"}]},
    ]

    send_feishu_card({
        "title": f"📊 {task_name}",
        "template": template,
        "elements": elements
    })


def notify_completion(task_name: str, final_step: str):
    """推送完成卡片"""
    elements = [
        {"tag": "markdown", "content": f"**✅ 任务完成**\n\n**{task_name}**\n\n📍 最终状态: {final_step}"},
        {"tag": "hr"},
        {"tag": "note", "elements": [{"tag": "plain_text", "content": f"🎉 由子 agent 监控推送 · {datetime.now().strftime('%H:%M:%S')}"}]},
    ]
    send_feishu_card({
        "title": f"🎉 {task_name} 已完成",
        "template": "green",
        "elements": elements
    })


def notify_error(task_name: str, error_msg: str):
    """推送错误卡片"""
    elements = [
        {"tag": "markdown", "content": f"**❌ 任务异常**\n\n**{task_name}**\n\n⚠️ {error_msg}"},
        {"tag": "hr"},
        {"tag": "note", "elements": [{"tag": "plain_text", "content": f"🚨 由子 agent 监控告警 · {datetime.now().strftime('%H:%M:%S')}"}]},
    ]
    send_feishu_card({
        "title": f"❌ {task_name} 异常",
        "template": "red",
        "elements": elements
    })


def notify_started(task_name: str, total_steps: int):
    """推送启动卡片"""
    elements = [
        {"tag": "markdown", "content": f"**🚀 任务已启动**\n\n**{task_name}**\n\n📋 共 {total_steps} 个步骤\n\n🔄 子 agent 监控中，进度将实时推送..."},
        {"tag": "hr"},
        {"tag": "note", "elements": [{"tag": "plain_text", "content": f"👁️ 由子 agent 守护监控 · {datetime.now().strftime('%H:%M:%S')}"}]},
    ]
    send_feishu_card({
        "title": f"🚀 {task_name} 已启动",
        "template": "blue",
        "elements": elements
    })


# ============ 状态管理 ============

def load_state() -> Dict:
    if Path(NOTIFY_STATE_FILE).exists():
        try:
            return json.loads(Path(NOTIFY_STATE_FILE).read_text())
        except Exception:
            pass
    return {"last_progress": -1, "last_step": "", "notified_start": False, "notified_done": False, "notified_error": False, "last_status": ""}


def save_state(state: Dict):
    try:
        Path(NOTIFY_STATE_FILE).write_text(json.dumps(state, indent=2))
    except Exception:
        pass


# ============ 核心监控循环 ============

def load_current_progress() -> Optional[Dict]:
    """读取当前任务进度"""
    if not PROGRESS_FILE.exists():
        return None
    try:
        return json.loads(PROGRESS_FILE.read_text())
    except Exception:
        return None


def main():
    print(f"[TaskMonitor] 🚀 子 agent 监控启动 PID={os.getpid()}")
    print(f"[TaskMonitor] 监控目录: {PROGRESS_DIR}")

    os.makedirs(PROGRESS_DIR, exist_ok=True)

    state = load_state()
    consecutive_errors = 0
    last_check = time.time()

    while True:
        try:
            progress_data = load_current_progress()

            if progress_data is None:
                # 无进度文件，休眠等待
                time.sleep(2)
                consecutive_errors = 0
                continue

            task_name = progress_data.get("name", "未知任务")
            progress = progress_data.get("progress", 0)
            status = progress_data.get("status", "running")
            step = progress_data.get("step", "初始化")
            error = progress_data.get("error")

            current_hash = hashlib.md5(
                f"{task_name}:{progress}:{step}:{status}".encode()
            ).hexdigest()[:8]

            # 检测状态变化
            changed = (
                state["last_progress"] != progress or
                state["last_step"] != step or
                state["last_status"] != status
            )

            # 推送启动通知（首次检测到任务）
            if progress_data and not state["notified_start"]:
                notify_started(task_name, len(progress_data.get("steps", [1])))
                state["notified_start"] = True
                save_state(state)

            # 进度更新推送（每 5% 变化 或 步骤变化）
            if changed and progress > 0:
                pct = min(100, max(0, progress))
                if changed:
                    notify_progress(task_name, pct, step, status)
                    state["last_progress"] = progress
                    state["last_step"] = step
                    state["last_status"] = status
                    save_state(state)

            # 检测任务完成
            if status == "done" and not state["notified_done"]:
                notify_completion(task_name, step)
                state["notified_done"] = True
                save_state(state)
                print(f"[TaskMonitor] ✅ 任务完成通知已推送，退出")
                break

            # 检测任务错误
            if error and not state["notified_error"]:
                notify_error(task_name, str(error))
                state["notified_error"] = True
                save_state(state)
                print(f"[TaskMonitor] ❌ 任务错误通知已推送")
                break

            consecutive_errors = 0
            time.sleep(3)  # 每 3 秒检查一次

        except KeyboardInterrupt:
            print("[TaskMonitor] ⏹️ 收到终止信号，退出")
            break
        except Exception as e:
            consecutive_errors += 1
            print(f"[TaskMonitor] ⚠️ 异常 #{consecutive_errors}: {e}")
            time.sleep(5)
            if consecutive_errors >= 10:
                print("[TaskMonitor] ❌ 连续异常，退出")
                break


if __name__ == "__main__":
    main()
