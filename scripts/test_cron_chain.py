#!/usr/bin/env python3
"""手动测试 cron-events → clawkeeper → 飞书 链路"""
import sys, os, json, urllib.request, urllib.error
sys.path.insert(0, '/root/.openclaw/workspace')
from clawkeeper.config_loader import get_webhook_url

# 读取刚才写入的事件
event_file = "/root/.openclaw/workspace/cron-events/记忆同步-18-30手动-20260422-125805.json"
with open(event_file, 'r') as f:
    data = json.load(f)

job_name = data.get('event', '未知任务')
status = data.get('action', 'fired')
message = data.get('message', '')
triggered_at = data.get('timestamp', '')

status_config = {
    'fired': ('🟢 任务触发', 'green'),
    'running': ('🔵 进行中', 'blue'),
    'done': ('✅ 任务完成', 'green'),
    'error': ('🔴 任务异常', 'red'),
}
title, color = status_config.get(status, ('📋 任务事件', 'grey'))

elements = [
    {"tag": "markdown", "content": f"**任务**: `{job_name}`"},
    {"tag": "markdown", "content": f"**状态**: `{status.upper()}`"},
]
if triggered_at:
    elements.append({"tag": "markdown", "content": f"**触发时间**: `{triggered_at}`"})
if message:
    elements.append({"tag": "markdown", "content": f"**详情**: {message}"})
elements.append({"tag": "hr"})
elements.append({"tag": "markdown", "content": "来源: `cron-events/` 监控（手动测试）"})

card = {
    "msg_type": "interactive",
    "card": {
        "header": {"title": {"tag": "plain_text", "content": title}, "template": color},
        "elements": elements
    }
}

webhook = get_webhook_url()
data = json.dumps(card, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(webhook, data=data, headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read())
        print(f"发送结果: {result}")
except Exception as e:
    print(f"发送失败: {e}")
