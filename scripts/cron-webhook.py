#!/usr/bin/env python3
"""
cron-webhook.py - 简化版webhook推送（供cron直接调用）
用法: python3 cron-webhook.py "标题" "内容" [颜色]
"""
import sys, os, json, urllib.request
from datetime import datetime

if os.path.exists('/etc/environment'):
    for line in open('/etc/environment'):
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            os.environ.setdefault(k, v.strip('"'))

APP_ID = os.environ.get("FEISHU_APP_ID", "cli_a96c9b5700f91bc9")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "${FEISHU_APP_SECRET}")
GROUP_ID = "os.environ.get("FEISHU_GROUP_ID", "YOUR_GROUP_ID")"

# get token
url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
data = json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode("utf-8")
req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
resp = urllib.request.urlopen(req, timeout=10)
token = json.loads(resp.read())["tenant_access_token"]

title = sys.argv[1] if len(sys.argv) > 1 else "Cron通知"
content = sys.argv[2] if len(sys.argv) > 2 else ""
color = sys.argv[3] if len(sys.argv) > 3 else "blue"

emojis = {"blue": "🔄", "green": "✅", "red": "⚠️", "orange": "🚨", "yellow": "🐟"}
emoji = emojis.get(color, "🔄")

card = {
    "receive_id": GROUP_ID,
    "msg_type": "interactive",
    "content": json.dumps({
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"{emoji} {title}"},
            "template": color
        },
        "elements": [
            {"tag": "markdown", "content": content.replace("\\n", "\n")},
            {"tag": "hr"},
            {"tag": "note", "elements": [{"tag": "plain_text", "content": f"AI调研 · {datetime.now().strftime('%H:%M:%S')}"}]}
        ]
    }, ensure_ascii=False)
}

msg_url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
req2 = urllib.request.Request(msg_url, data=json.dumps(card).encode("utf-8"),
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
with urllib.request.urlopen(req2, timeout=10) as resp2:
    result = json.loads(resp2.read())
    if result.get("code") == 0:
        print(f"✅ 推送成功: {title}")
    else:
        print(f"❌ 推送失败: {result}")
