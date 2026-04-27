#!/usr/bin/env python3
import subprocess, os, json
from datetime import datetime

webhook = "YOUR_FEISHU_WEBHOOK_URL"

def push(title, content, color="blue"):
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": title}, "template": color},
            "elements": [{"tag": "markdown", "content": content}]
        }
    }
    data = json.dumps(card, ensure_ascii=False).encode()
    req = urllib.request.Request(webhook, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            print(r.read())
    except Exception as e:
        print(f"Error: {e}")

import urllib.request
push("🔍 task_agent 诊断开始", "正在检查进程状态...", "blue")
