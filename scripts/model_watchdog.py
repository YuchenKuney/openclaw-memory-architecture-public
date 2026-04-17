#!/usr/bin/env python3
"""
模型看门狗 - 自动监控模型状态，失败自动切换
检测 MiniMax 为主要模型，失败自动切 DeepSeek
重要事件发送到飞书群
"""

import urllib.request
import urllib.error
import json
import subprocess
import sys
import os
from datetime import datetime

LOG = "/root/.openclaw/workspace/memory/model_watchdog.log"
CONFIG = "/root/.openclaw/openclaw.json"

# 飞书群 Webhook
FEISHU_GROUP_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/18752a31-9cc7-47f5-9a41-d50261934f6e"
FEISHU_GROUP_ID = "oc_975800947a16567e79f0130cfac65aa3"

# 备用通知 Webhook（服务器汇报群）
SERVER_REPORT_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/18752a31-9cc7-47f5-9a41-d50261934f6e"

MINIMAX = {
    "url": "https://api.minimaxi.com/anthropic/v1/messages",
    "key": "sk-cp-QRI7FFwxiGyHSR7S_7LTpkEjbtClAtAdWpHvBg3Iun-6BcLkxGU16vvvQuIjFVms4tCbNy3TnkMSw3z73j7ApkWMji3c7g_1d-YHCTSnEZNFSfeDqmT7TKk"
}

DEEPSEEK = {
    "url": "https://api.deepseek.com/chat/completions",
    "key": "sk-6facfc8c1ab54118a46ac2ff6a185064"
}

FAIL_COUNT_FILE = "/root/.openclaw/workspace/memory/model_fail_count.json"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = "[%s] %s" % (ts, msg)
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def send_feishu(text, webhook=None):
    """发送飞书通知"""
    if webhook is None:
        webhook = FEISHU_GROUP_WEBHOOK
    
    payload = json.dumps({"msg_type": "text", "content": {"text": text}}, ensure_ascii=False)
    try:
        proc = subprocess.Popen(
            ["curl", "-s", "-X", "POST", webhook,
             "-H", "Content-Type: application/json",
             "-d", payload],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        proc.communicate()
        log(f"飞书通知已发送: {text[:50]}...")
    except Exception as e:
        log(f"飞书通知失败: {str(e)}")

def send_model_alert(title, content):
    """发送模型告警到群"""
    msg = f"🤖 模型监控告警\n\n📌 {title}\n\n{content}\n\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    send_feishu(msg)

def test_minimax():
    try:
        data = json.dumps({
            "model": "auto",
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "hi"}]
        }).encode()
        req = urllib.request.Request(
            MINIMAX["url"], data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + MINIMAX["key"],
                "anthropic-version": "2023-06-01"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception as e:
        log("MiniMax检测失败: " + str(e))
        return False

def test_deepseek():
    try:
        data = json.dumps({
            "model": "deepseek-chat",
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "hi"}]
        }).encode()
        req = urllib.request.Request(
            DEEPSEEK["url"], data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + DEEPSEEK["key"]
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception as e:
        log("DeepSeek检测失败: " + str(e))
        return False

def get_fail_count():
    if not os.path.exists(FAIL_COUNT_FILE):
        return {"minimax": 0, "deepseek": 0}
    try:
        with open(FAIL_COUNT_FILE) as f:
            return json.load(f)
    except:
        return {"minimax": 0, "deepseek": 0}

def save_fail_count(data):
    with open(FAIL_COUNT_FILE, "w") as f:
        json.dump(data, f)

def get_current_model():
    try:
        with open(CONFIG) as f:
            cfg = json.load(f)
        return cfg.get("agents", {}).get("defaults", {}).get("model", {}).get("primary", "deepseek/deepseek-chat")
    except:
        return "deepseek/deepseek-chat"

def switch_to(model_name, label):
    try:
        with open(CONFIG) as f:
            cfg = json.load(f)
        cfg.setdefault("agents", {}).setdefault("defaults", {}).setdefault("model", {})["primary"] = model_name
        with open(CONFIG, "w") as f:
            json.dump(cfg, f)
        log("已切换到 " + label + " (" + model_name + ")")
        
        # 发送飞书群通知
        send_model_alert(
            f"模型自动切换: {label}",
            f"检测到主模型异常，已自动切换到 {model_name}\n如需手动切换可随时告诉我"
        )
        
        # 重启网关
        r = subprocess.run(["openclaw", "gateway", "restart"],
            capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            log("Gateway重启成功")
        else:
            log("Gateway重启: " + r.stderr[:100])
        return True
    except Exception as e:
        log("切换失败: " + str(e))
        send_model_alert("模型切换失败", f"尝试切换到 {model_name} 失败: {str(e)}")
        return False

def main():
    log("=== 模型看门狗启动 ===")
    current = get_current_model()
    fail = get_fail_count()
    log("当前主模型: " + current + " 失败计数: minimax=" + str(fail["minimax"]) + " deepseek=" + str(fail["deepseek"]))

    if "deepseek" in current:
        if test_deepseek():
            if fail["deepseek"] > 0:
                # 之前失败过，现在恢复了
                send_model_alert(
                    "DeepSeek 恢复",
                    f"DeepSeek 模型已恢复正常\n当前模型: {current}"
                )
                log("DeepSeek 恢复")
            fail["deepseek"] = 0
            save_fail_count(fail)
            log("DeepSeek 正常")
        else:
            fail["deepseek"] += 1
            save_fail_count(fail)
            log("DeepSeek 失败 " + str(fail["deepseek"]) + "/3")
            
            if fail["deepseek"] == 1:
                send_model_alert(
                    "DeepSeek 异常",
                    f"DeepSeek 模型检测失败 1/3\n等待下次检测..."
                )
            elif fail["deepseek"] >= 3:
                send_model_alert(
                    "DeepSeek 连续失败",
                    f"DeepSeek 模型连续失败 {fail['deepseek']} 次，准备切换..."
                )
                if test_minimax():
                    switch_to("minimax/auto", "MiniMax")
                else:
                    log("两个模型都挂了，保留DeepSeek等待恢复")
                    send_model_alert(
                        "模型告警",
                        f"DeepSeek 和 MiniMax 都不可用\n保留 DeepSeek 等待恢复"
                    )
    else:
        if test_minimax():
            if fail["minimax"] > 0:
                send_model_alert(
                    "MiniMax 恢复",
                    f"MiniMax 模型已恢复正常\n当前模型: {current}"
                )
                log("MiniMax 恢复")
            fail["minimax"] = 0
            save_fail_count(fail)
            log("MiniMax 正常")
        else:
            fail["minimax"] += 1
            save_fail_count(fail)
            log("MiniMax 失败 " + str(fail["minimax"]) + "/3")
            
            if fail["minimax"] == 1:
                send_model_alert(
                    "MiniMax 异常",
                    f"MiniMax 模型检测失败 1/3\n等待下次检测..."
                )
            elif fail["minimax"] >= 3:
                send_model_alert(
                    "MiniMax 连续失败",
                    f"MiniMax 模型连续失败 {fail['minimax']} 次，准备切换..."
                )
                if test_deepseek():
                    switch_to("deepseek/deepseek-chat", "DeepSeek")
                else:
                    log("两个模型都挂了，保留MiniMax等待恢复")
                    send_model_alert(
                        "模型告警",
                        f"MiniMax 和 DeepSeek 都不可用\n保留 MiniMax 等待恢复"
                    )
    log("=== 模型看门狗完成 ===")

if __name__ == "__main__":
    main()
