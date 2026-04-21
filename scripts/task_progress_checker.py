#!/usr/bin/env python3
"""
任务进度检查器（Cron 调用）

每3分钟检查一次 .task_state.json
如果有活跃任务 → 发送飞书卡片汇报进度
如果没有任务 → 静默退出（不打扰坤哥）
"""

import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

STATE_FILE = Path("/root/.openclaw/workspace/.task_state.json")
WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/7a939580-e987-4571-a142-f58528cf71ec"


def read_state():
    if not STATE_FILE.exists():
        return None
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return None


def build_progress_bar(current: int, total: int) -> str:
    filled = round(current / total * 10)
    return "█" * filled + "░" * (10 - filled)


def send_feishu_card(state: dict):
    task = state["task"]
    total = state["total_steps"]
    step = state.get("current_step", 0)
    step_name = state.get("step_name", "进行中")
    next_step = state.get("next_step", "")
    progress = state.get("progress", round(step / total * 100))
    eta = state.get("eta_seconds", 0)
    last_updated = state.get("last_updated", "")
    status = state.get("status", "running")

    bar = build_progress_bar(step, total)

    # 颜色
    if status == "done":
        color, template = "✅ 任务完成", "green"
    elif status == "error":
        color, template = "🔴 任务出错", "red"
    else:
        color, template = "🔄 进行中", "orange"

    elements = [
        {
            "tag": "markdown",
            "content": f"**🤖 当前任务**: `{task}`"
        },
        {
            "tag": "markdown",
            "content": f"**{color}**: {bar} **{progress}%**"
        },
        {
            "tag": "markdown",
            "content": f"**📍 当前**: Step {step}/{total} — `{step_name}`"
        },
    ]

    if next_step:
        elements.append({
            "tag": "markdown",
            "content": f"**➡️  下一步**: `{next_step}`"
        })

    if eta > 0:
        eta_text = f"约 {eta} 秒" if eta < 60 else f"约 {eta // 60} 分钟"
        elements.append({
            "tag": "markdown",
            "content": f"**⏱️  预计**: {eta_text} 后完成"
        })

    elements.extend([
        {
            "tag": "markdown",
            "content": f"**🕐 最后更新**: `{last_updated}`"
        },
        {"tag": "hr"},
        {
            "tag": "markdown",
            "content": "_每3分钟自动汇报任务进度_"
        }
    ])

    if status == "done":
        msg = state.get("completion_message", "")
        if msg:
            elements.insert(2, {
                "tag": "markdown",
                "content": f"**📝 总结**: {msg}"
            })
    elif status == "error":
        err = state.get("error_message", "")
        elements.insert(2, {
            "tag": "markdown",
            "content": f"**❌ 错误**: `{err}`"
        })

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"{color} | {task}"},
                "template": template,
            },
            "elements": elements
        }
    }

    try:
        data = json.dumps(card, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            WEBHOOK,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            sc = result.get("StatusCode") or result.get("code")
            print(f"[task_progress_checker] 进度已汇报: status={sc}")
            return sc == 0
    except Exception as e:
        print(f"[task_progress_checker] 发送失败: {e}")
        return False


def main():
    state = read_state()

    if not state:
        # 没有任务，静默退出
        sys.exit(0)

    status = state.get("status", "running")

    # 只有 running 状态才发进度
    # done/error 状态只发一次，然后清除
    if status == "running":
        send_feishu_card(state)
    elif status in ("done", "error"):
        send_feishu_card(state)
        # 发送后清除状态（避免重复发送）
        STATE_FILE.unlink(missing_ok=True)
        print(f"[task_progress_checker] 状态已清除 ({status})")


if __name__ == "__main__":
    main()
