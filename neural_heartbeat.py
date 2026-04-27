#!/usr/bin/env python3
"""
neural_heartbeat.py - 神经层心跳守护

每30秒检测所有节点存活状态，更新心跳
超时标记offline，触发恢复机制
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional

WORKSPACE = Path("/root/.openclaw/workspace")
NODES_FILE = WORKSPACE / "neural_nodes.json"
HB_FILE = WORKSPACE / "neural_heartbeat.json"
STATUS_FILE = WORKSPACE / "neural_status.json"

HEARTBEAT_INTERVAL = 30  # 秒
HEARTBEAT_TIMEOUT = 120  # 秒（超过则标记offline）
MAX_CONSECUTIVE_FAILS = 3


class NeuralHeartbeat:
    """神经层心跳监控"""

    def __init__(self):
        self.nodes: Dict[str, dict] = {}
        self.last_heartbeats: Dict[str, str] = {}  # node -> last hb time
        self.fail_counts: Dict[str, int] = {}  # node -> consecutive fail count
        self.load_nodes()

    def load_nodes(self):
        if NODES_FILE.exists():
            try:
                data = json.loads(NODES_FILE.read_text())
                for d in data.get("nodes", []):
                    self.nodes[d["name"]] = d
                    self.fail_counts[d["name"]] = 0
            except Exception:
                pass

    def save_status(self):
        """保存状态到文件"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "nodes": {},
            "summary": {
                "total": len(self.nodes),
                "online": 0,
                "offline": 0,
            }
        }
        for name, node_data in self.nodes.items():
            last_hb = self.last_heartbeats.get(name)
            node_status = "offline"
            if last_hb:
                try:
                    hb_time = datetime.fromisoformat(last_hb)
                    if (datetime.now() - hb_time).total_seconds() < HEARTBEAT_TIMEOUT:
                        node_status = "online"
                        status["summary"]["online"] += 1
                    else:
                        status["summary"]["offline"] += 1
                except Exception:
                    status["summary"]["offline"] += 1
            else:
                status["summary"]["offline"] += 1

            status["nodes"][name] = {
                **node_data,
                "heartbeat_status": node_status,
                "last_heartbeat": last_hb,
                "fail_count": self.fail_counts.get(name, 0),
            }

        STATUS_FILE.write_text(json.dumps(status, indent=2, ensure_ascii=False))
        return status

    def check_node(self, name: str, vpn_ip: str, public_ip: str = "") -> bool:
        """检查单个节点存活"""
        # 优先ping VPN IP
        for ip in [vpn_ip, public_ip]:
            if not ip:
                continue
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", ip],
                capture_output=True
            )
            if result.returncode == 0:
                return True
        return False

    def ping_node(self, name: str, vpn_ip: str, public_ip: str = "") -> Optional[dict]:
        """通过SSH发送ping信号"""
        for ip in [vpn_ip, public_ip]:
            if not ip:
                continue
            result = subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
                 "-i", "/root/.ssh/id_ed25519",
                 f"root@{ip}", "echo pong"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return {"status": "ok", "ip": ip}
        return None

    def beat(self) -> dict:
        """执行一次心跳检测"""
        results = {}
        for name, node_data in list(self.nodes.items()):
            if name == "brain":
                self.last_heartbeats["brain"] = datetime.now().isoformat()
                continue

            vpn_ip = node_data.get("vpn_ip", "")
            public_ip = node_data.get("public_ip", "")

            # SSH ping测试
            ping_result = self.ping_node(name, vpn_ip, public_ip)

            if ping_result:
                self.last_heartbeats[name] = datetime.now().isoformat()
                self.fail_counts[name] = 0
                results[name] = {"status": "online", "ip": ping_result.get("ip")}
            else:
                self.fail_counts[name] = self.fail_counts.get(name, 0) + 1
                results[name] = {
                    "status": "offline",
                    "fail_count": self.fail_counts[name],
                }
                if self.fail_counts[name] >= MAX_CONSECUTIVE_FAILS:
                    print(f"[NeuralHeartbeat] ⚠️ 节点 {name} 已连续失败 {MAX_CONSECUTIVE_FAILS} 次")

        status = self.save_status()
        return results

    def run_daemon(self, interval: int = HEARTBEAT_INTERVAL):
        """持续运行心跳守护"""
        print(f"[NeuralHeartbeat] 🧠 心跳守护启动（每{interval}秒检测一次）")
        print(f"[NeuralHeartbeat] 监控节点: {list(self.nodes.keys())}")

        while True:
            try:
                results = self.beat()
                now = datetime.now().strftime("%H:%M:%S")
                online = sum(1 for r in results.values() if r.get("status") == "online")
                print(f"[{now}] 心跳检测: {'✅ ' if online == len(results) else '⚠️ '}{online}/{len(results)} 在线")
                time.sleep(interval)
            except KeyboardInterrupt:
                print("\n[NeuralHeartbeat] 心跳守护停止")
                break
            except Exception as e:
                print(f"[NeuralHeartbeat] 异常: {e}")
                time.sleep(interval)


def main():
    hb = NeuralHeartbeat()

    if "--once" in sys.argv:
        # 单次心跳检测
        results = hb.beat()
        print(json.dumps(results, indent=2))
    else:
        # 持续守护模式
        interval = int(sys.argv[1]) if len(sys.argv) > 1 else HEARTBEAT_INTERVAL
        hb.run_daemon(interval)


if __name__ == "__main__":
    main()