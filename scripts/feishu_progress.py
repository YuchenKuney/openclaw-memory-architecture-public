#!/usr/bin/env python3
"""
Feishu Progress Notifier - 群聊实时进度通知
用法:
    python3 feishu_progress.py <job_name> <progress> <step> [message]

示例:
    python3 feishu_progress.py "记忆同步" 0 "开始执行"
    python3 feishu_progress.py "记忆同步" 25 "读取记忆文件"
    python3 feishu_progress.py "记忆同步" 100 "同步完成"

进度条 emoji:
    0-10%:  🆕 开始
    11-25%: █░░░░░░░░░  10%
    26-50%: ███░░░░░░░  30%
    51-75%: █████░░░░░  60%
    76-99%: ███████░░░  80%
    100%:   ██████████  100%
"""

import sys
import json
import os
import urllib.request
import urllib.error
from datetime import datetime

# 飞书群聊 Webhook（环境变量优先）
FEISHU_GROUP_WEBHOOK = os.environ.get(
    "FEISHU_GROUP_WEBHOOK",
    "https://open.feishu.cn/open-apis/bot/v2/hook/7a939580-e987-4571-a142-f58528cf71ec"
)

# 群 ID（仅用于记录，不影响发送）
GROUP_ID = os.environ.get("FEISHU_GROUP_ID", "")


def build_progress_bar(progress: int) -> str:
    """构建可视化进度条（10格）"""
    filled = round(progress / 10)
    empty = 10 - filled
    return "█" * filled + "░" * empty


def send_feishu_card(job_name: str, progress: int, step: str, message: str = ""):
    """
    发送飞书进度卡片到群聊
    """
    now = datetime.now().strftime("%H:%M:%S")

    # 进度条
    bar = build_progress_bar(progress)

    # 进度文案
    if progress == 0:
        status_text = "🆕 开始执行"
        color = "blue"
    elif progress == 100:
        status_text = "✅ 任务完成"
        color = "green"
    else:
        status_text = f"🔄 进行中"
        color = "orange"

    # 步骤标题
    header_title = f"{status_text} {job_name}"

    # 消息体
    content_parts = [
        f"**任务**: `{job_name}`",
        f"**进度**: {bar} `{progress}%`",
        f"**步骤**: `{step}`",
    ]
    if message:
        content_parts.append(f"**详情**: {message}")
    content_parts.append(f"`⏰ {now}`")

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": header_title},
                "template": color,
            },
            "elements": [
                {"tag": "markdown", "content": "\n".join(content_parts)},
            ]
        }
    }

    return card


def send(card):
    """发送卡片到飞书"""
    data = json.dumps(card).encode("utf-8")
    req = urllib.request.Request(
        FEISHU_GROUP_WEBHOOK,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("code") == 0 or result.get("StatusCode") == 0:
                print(f"[Feishu] ✅ 发送成功")
                return True
            else:
                print(f"[Feishu] ❌ 发送失败: {result}")
                return False
    except urllib.error.URLError as e:
        print(f"[Feishu] ❌ 网络错误: {e}")
        return False
    except Exception as e:
        print(f"[Feishu] ❌ 异常: {e}")
        return False


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    job_name = sys.argv[1]
    try:
        progress = int(sys.argv[2])
    except ValueError:
        print("进度必须是 0-100 的整数")
        sys.exit(1)
    step = sys.argv[3]
    message = sys.argv[4] if len(sys.argv) > 4 else ""

    if not 0 <= progress <= 100:
        print("进度必须在 0-100 之间")
        sys.exit(1)

    card = send_feishu_card(job_name, progress, step, message)
    send(card)


if __name__ == "__main__":
    main()
