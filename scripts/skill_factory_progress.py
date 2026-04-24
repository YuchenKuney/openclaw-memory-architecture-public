#!/usr/bin/env python3
"""
feishu_progress.py - 通用 Webhook 进度推送脚本

用法：
  python3 feishu_progress.py <标题> <内容> [颜色]

颜色选项：
  blue   - 进行中（默认）
  green  - 成功/完成
  red    - 失败/错误
  yellow - 警告

示例：
  python3 feishu_progress.py "Step 1/3: 创建Skill" "✅ market_researcher已创建" "blue"
  python3 feishu_progress.py "✅ 完成" "竞品分析报告已生成" "green"
  python3 feishu_progress.py "❌ 失败" "网络超时" "red"

环境变量：
  FEISHU_WEBHOOK    飞书 Webhook 地址（必填）
  FEISHU_SECRET     飞书加签密钥（可选）
"""

import os
import sys
import time
import hmac
import hashlib
import base64
import json
import requests
from urllib.parse import urlencode

# ══════════════════════════════════════════════════════════════
# 配置
# ══════════════════════════════════════════════════════════════

WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "")
WEBHOOK_SECRET = os.environ.get("FEISHU_SECRET", "")

# ══════════════════════════════════════════════════════════════
# 飞书签名（可选）
# ══════════════════════════════════════════════════════════════

def generate_sign(secret: str, timestamp: int) -> str:
    """生成飞书签名"""
    string_to_sign = f"{timestamp}\n{secret}"
    secret_encoded = string_to_sign.encode("utf-8")
    sign = hmac.new(
        secret_encoded,
        secret_encoded,
        digestmod=hashlib.sha256
    ).digest()
    return base64.b64encode(sign).decode("utf-8")


def build_payload(title: str, content: str, color: str = "blue") -> dict:
    """构建飞书卡片 payload"""
    color_map = {
        "blue": "blue",
        "green": "green",
        "red": "red",
        "yellow": "yellow",
        "purple": "purple",
        "orange": "orange",
        "grey": "grey"
    }

    template = color_map.get(color, "blue")

    # 构建卡片元素
    elements = [
        {
            "tag": "markdown",
            "content": content
        },
        {
            "tag": "note",
            "elements": [
                {"tag": "plain_text", "content": f"⏰ {time.strftime('%H:%M:%S')}"}
            ]
        }
    ]

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title
                },
                "template": template
            },
            "elements": elements
        }
    }


def push(title: str, content: str, color: str = "blue") -> bool:
    """推送飞书卡片"""
    if not WEBHOOK:
        # 无 Webhook 时打印到控制台
        emoji_map = {"blue": "🔵", "green": "🟢", "red": "🔴", "yellow": "🟡"}
        emoji = emoji_map.get(color, "🔵")
        print(f"{emoji} {title}")
        for line in content.split("\n"):
            print(f"   {line}")
        return True

    payload = build_payload(title, content, color)

    headers = {"Content-Type": "application/json"}

    try:
        resp = requests.post(
            WEBHOOK,
            json=payload,
            headers=headers,
            timeout=10
        )
        result = resp.json()

        if result.get("code") == 0 or resp.status_code == 200:
            return True
        else:
            print(f"❌ 推送失败: {result.get('msg', '未知错误')}")
            return False

    except requests.exceptions.Timeout:
        print("❌ 推送超时")
        return False
    except Exception as e:
        print(f"❌ 推送异常: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: feishu_progress.py <标题> <内容> [颜色]")
        print("示例: feishu_progress.py 'Step 1/3' '正在创建...' blue")
        sys.exit(1)

    title = sys.argv[1]
    content = sys.argv[2]
    color = sys.argv[3] if len(sys.argv) > 3 else "blue"

    success = push(title, content, color)
    sys.exit(0 if success else 1)
