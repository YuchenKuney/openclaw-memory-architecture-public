#!/usr/bin/env python3
"""
feishu_progress.py - 飞书进度推送（反黑箱专用，不走主会话）

用法：
    python3 feishu_progress.py "Step 2/5: 竞争格局" "Shopee 第1，TikTok 第2" "blue"

颜色模板：blue=进行中, green=完成, red=警告, purple=最终报告
"""
import sys, os, json, urllib.request
from datetime import datetime

# 加载环境变量
if os.path.exists('/etc/environment'):
    with open('/etc/environment') as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                v = v.strip('"')
                os.environ.setdefault(k, v)

# Webhook方式（优先，坤哥配置）
WEBHOOK_URL = os.environ.get(
    "FEISHU_WEBHOOK",
    "https://open.feishu.cn/open-apis/bot/v2/hook/e1e47866-19f3-4851-a954-68bda533e990"
)

TEMPLATE_COLORS = {
    "blue": "blue",
    "green": "green",
    "red": "red",
    "purple": "purple",
    "orange": "orange",
}

def send_progress(step_title: str, content: str, color: str = "blue", done: bool = False):
    """发送进度卡片到飞书群（使用Webhook）"""
    color = TEMPLATE_COLORS.get(color, "blue")

    if done:
        emoji = "✅"
    elif "完成" in step_title or "done" in step_title.lower():
        emoji = "✅"
    elif "进行" in step_title or "ing" in step_title.lower():
        emoji = "🔄"
    elif "警告" in step_title or "错误" in step_title:
        emoji = "⚠️"
    elif "汇总" in step_title or "报告" in step_title or "最终" in step_title:
        emoji = "📊"
    else:
        emoji = "🔄"

    # 构建卡片消息
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"{emoji} {step_title}"},
            "template": color
        },
        "elements": [
            {"tag": "markdown", "content": content},
            {"tag": "hr"},
            {
                "tag": "note",
                "elements": [
                    {"tag": "plain_text", "content": f"AI 调研进度 · {datetime.now().strftime('%H:%M:%S')}"}
                ]
            }
        ]
    }

    data = {
        "msg_type": "interactive",
        "card": card
    }

    req = urllib.request.Request(
        WEBHOOK_URL,
        data=json.dumps(data, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("code") == 0 or result.get("StatusCode") == 0:
                print(f"✅ 推送成功: {step_title}")
            else:
                print(f"⚠️ 推送失败: {result}")
    except Exception as e:
        print(f"❌ 推送异常: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python3 feishu_progress.py <标题> <内容> [颜色] [done]")
        print("例: python3 feishu_progress.py 'Step 1/5: 市场规模' 'GMV $57亿' blue")
        sys.exit(1)

    title = sys.argv[1]
    content = sys.argv[2]
    color = sys.argv[3] if len(sys.argv) > 3 else "blue"
    done = sys.argv[4].lower() == "true" if len(sys.argv) > 4 else False

    send_progress(title, content, color, done)