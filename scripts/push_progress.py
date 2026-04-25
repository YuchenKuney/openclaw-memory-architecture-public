#!/usr/bin/env python3
import sys, os, json, urllib.request
if os.path.exists('/etc/environment'):
    with open('/etc/environment') as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                v = v.strip('"')
                os.environ.setdefault(k, v)

APP_ID = os.environ.get("FEISHU_APP_ID", "cli_a96c9b5700f91bc9")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "${FEISHU_APP_SECRET}")
GROUP_ID = "os.environ.get("FEISHU_GROUP_ID", "YOUR_GROUP_ID")"

# get token
url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
data = json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode("utf-8")
req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=10) as resp:
    result = json.loads(resp.read())
    if result.get("code") != 0:
        print(f"Token failed: {result}"); sys.exit(1)
    token = result["tenant_access_token"]

title = sys.argv[1] if len(sys.argv) > 1 else "进度"
content = sys.argv[2] if len(sys.argv) > 2 else ""
color = sys.argv[3] if len(sys.argv) > 3 else "blue"

emojis = {"blue": "🔄", "green": "✅", "red": "⚠️", "orange": "🚨"}
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
            {"tag": "note", "elements": [{"tag": "plain_text", "content": f"AI调研进度 · {__import__('datetime').datetime.now().strftime('%H:%M:%S')}"}]}
        ]
    }, ensure_ascii=False)
}

msg_url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
req = urllib.request.Request(msg_url, data=json.dumps(card).encode("utf-8"),
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}, method="POST")
with urllib.request.urlopen(req, timeout=10) as resp:
    result = json.loads(resp.read())
    print(f"✅" if result.get("code") == 0 else f"❌ {result}")
