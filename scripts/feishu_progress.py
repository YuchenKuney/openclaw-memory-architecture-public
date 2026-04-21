#!/usr/bin/env python3
"""
feishu_progress.py - 飞书进度推送（反黑箱专用，不走主会话）

用法：
    python3 feishu_progress.py "Step 2/5: 竞争格局" "Shopee 第1，TikTok 第2" "blue"

颜色模板：blue=进行中, green=完成, red=警告, purple=最终报告
"""
import sys
import json
import urllib.request
from datetime import datetime

WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/375a8be1-9e3e-4758-a78b-e775fd4d32a1"

TEMPLATE_COLORS = {
    "blue": "blue",     # 进行中
    "green": "green",   # 完成
    "red": "red",       # 警告/错误
    "purple": "purple", # 最终报告
    "orange": "orange", # 等待中
}

def send_progress(step_title: str, content: str, color: str = "blue", done: bool = False):
    """发送进度卡片到飞书群"""
    color = TEMPLATE_COLORS.get(color, "blue")
    
    # Emoji 前缀
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
    
    card = {
        "msg_type": "interactive",
        "card": {
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
    }
    
    payload = json.dumps(card, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(WEBHOOK, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
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
