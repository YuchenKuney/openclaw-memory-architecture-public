#!/usr/bin/env python3
"""
neural_node_service.py - 节点端神经服务（部署到新加坡）
在中枢注册，并处理从中枢发来的信号
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

SIGNAL_FILE = Path("/root/.openclaw/workspace/neural_signals/incoming.json")
SIGNAL_FILE.parent.mkdir(exist_ok=True)


def handle_signal(signal_dict: dict) -> dict:
    """处理从中枢发来的信号"""
    signal_type = signal_dict.get("type", signal_dict.get("signal_type", ""))
    payload = signal_dict.get("payload", signal_dict.get("args", {}))
    to_node = signal_dict.get("to", "singapore")

    # ping - 响应连接测试
    if signal_type == "ping":
        return {"status": "ok", "pong": True, "node": "singapore", "timestamp": datetime.now().isoformat()}

    # status - 返回节点状态
    if signal_type == "status" or (isinstance(payload, dict) and payload.get("type") == "status"):
        uptime_result = subprocess.run("uptime -p", shell=True, capture_output=True, text=True)
        load_result = subprocess.run("cat /proc/loadavg", shell=True, capture_output=True, text=True)
        return {
            "status": "ok",
            "node": "singapore",
            "role": "worker",
            "uptime": uptime_result.stdout.strip(),
            "load": load_result.stdout.strip(),
            "timestamp": datetime.now().isoformat(),
        }

    # exec - 执行命令
    if signal_type == "exec" or (isinstance(payload, dict) and payload.get("type") == "exec"):
        cmd = payload.get("args", {}).get("command", "") if isinstance(payload, dict) else payload.get("command", "")
        if not cmd and isinstance(payload, dict):
            cmd = payload.get("command", payload.get("cmd", ""))
        if not cmd:
            return {"status": "ok", "output": "no command provided"}
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return {
            "status": "ok",
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:500],
            "returncode": result.returncode,
        }

    # sense - 系统感知
    if signal_type == "sense" or (isinstance(payload, dict) and payload.get("type") == "sense"):
        sense_type = payload.get("sense_type", "system") if isinstance(payload, dict) else "system"
        if sense_type == "system":
            cpu = subprocess.run("cat /proc/loadavg 2>/dev/null | awk '{print $1,$2,$3}'", shell=True, capture_output=True, text=True)
            mem = subprocess.run("free -m | awk 'NR==2{print $3\"MB/\"$2\"MB\"}'", shell=True, capture_output=True, text=True)
            disk = subprocess.run("df -h / | tail -1 | awk '{print $5,$4}'", shell=True, capture_output=True, text=True)
            return {
                "status": "ok",
                "sense_type": "system",
                "cpu": cpu.stdout.strip(),
                "memory": mem.stdout.strip(),
                "disk": disk.stdout.strip(),
                "node": "singapore",
                "timestamp": datetime.now().isoformat(),
            }

    # register_reflex - 注册条件反射弧
    if signal_type == "register_reflex":
        condition = payload.get("condition", "") if isinstance(payload, dict) else ""
        action = payload.get("action", {}) if isinstance(payload, dict) else {}
        reflex_file = Path("/root/.openclaw/workspace/neural_reflexes.json")
        reflexes = json.loads(reflex_file.read_text()) if reflex_file.exists() else {}
        reflexes[signal_dict.get("signal_id", str(time.time()))] = {
            "condition": condition,
            "action": action,
            "created": datetime.now().isoformat(),
        }
        reflex_file.write_text(json.dumps(reflexes, indent=2))
        return {"status": "ok", "reflex_registered": True}

    return {"status": "ok", "processed": signal_type}


def main():
    """节点服务主循环"""
    print("[NeuralNode] 🧠 新加坡节点服务启动")

    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        # 单次处理模式（从STDIN读取信号）
        if not sys.stdin.isatty():
            signal_json = sys.stdin.read().strip()
            if signal_json:
                try:
                    signal_dict = json.loads(signal_json)
                    result = handle_signal(signal_dict)
                    print(json.dumps(result))
                except json.JSONDecodeError:
                    print(json.dumps({"status": "error", "message": "invalid json"}))
        return

    # 持续监听模式（读取incoming.json文件）
    print("[NeuralNode] 📡 进入监听模式，等待中枢信号...")
    last_mtime = 0

    while True:
        try:
            if SIGNAL_FILE.exists():
                mtime = SIGNAL_FILE.stat().st_mtime
                if mtime != last_mtime:
                    last_mtime = mtime
                    signal_json = SIGNAL_FILE.read_text().strip()
                    if signal_json:
                        try:
                            signal_dict = json.loads(signal_json)
                            result = handle_signal(signal_dict)
                            response_file = SIGNAL_FILE.parent / "response.json"
                            response_file.write_text(json.dumps(result))
                            SIGNAL_FILE.unlink()  # 处理完成后删除信号文件
                        except json.JSONDecodeError:
                            pass
            time.sleep(1)
        except KeyboardInterrupt:
            print("\n[NeuralNode] 服务停止")
            break
        except Exception as e:
            print(f"[NeuralNode] 异常: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()