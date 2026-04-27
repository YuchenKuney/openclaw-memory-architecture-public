#!/usr/bin/env python3
"""
neural_main.py - 神经层总控（中枢端）

整合神经层所有模块，提供统一接口

功能：
1. 节点管理（注册/注销/状态）
2. 信号传输（signal/broadcast）
3. 分布式感知（sense）
4. 条件反射（reflex）
5. 心跳监控（heartbeat）

用法：
    from neural_main import NeuralSystem
    neural = NeuralSystem()
    neural.status()                    # 查看所有节点
    neural.signal("singapore", "ping") # 发送信号
    neural.sense_all()                 # 感知所有节点
    neural.register_reflex("cpu>80", alert)  # 注册反射弧
"""

import os
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

WORKSPACE = Path("/root/.openclaw/workspace")
NODES_FILE = WORKSPACE / "neural_nodes.json"


class NeuralSystem:
    """神经层总控系统"""

    def __init__(self):
        self.layer = None
        self.protocol = None
        self.heartbeat = None
        self.reflex = None
        self._init_modules()

    def _init_modules(self):
        """初始化所有模块"""
        try:
            from neural_layer import NeuralLayer
            from neural_protocol import SignalProtocol
            from neural_heartbeat import NeuralHeartbeat
            from neural_reflex import ReflexRegistry

            self.layer = NeuralLayer()
            self.protocol = SignalProtocol(self.layer)
            self.heartbeat = NeuralHeartbeat()
            self.reflex = ReflexRegistry()

            print(f"[NeuralSystem] ✅ 神经层初始化完成")
            print(f"    节点数: {len(self.layer.nodes)}")
            print(f"    反射弧: {len(self.reflex.arcs)}")
        except ImportError as e:
            print(f"[NeuralSystem] ❌ 模块导入失败: {e}")

    def status(self) -> dict:
        """获取系统状态"""
        node_status = self.layer.get_status() if self.layer else {}
        hb_status = {}
        if self.heartbeat:
            hb_status = {
                "nodes": list(self.layer.nodes.keys()) if self.layer else [],
                "heartbeat_interval": "30s",
                "timeout": "120s",
            }

        reflex_arcs = []
        if self.reflex:
            for arc in self.reflex.arcs.values():
                reflex_arcs.append({
                    "id": arc.arc_id,
                    "name": arc.name,
                    "condition": arc.condition.describe(),
                    "enabled": arc.enabled,
                })

        return {
            "timestamp": datetime.now().isoformat(),
            "nodes": node_status,
            "heartbeat": hb_status,
            "reflex_arcs": reflex_arcs,
        }

    def signal(self, target: str, command: str, args: dict = None) -> Optional[dict]:
        """发送神经冲动"""
        if self.protocol:
            return self.protocol.signal(target, command, args)
        return None

    def broadcast(self, message: dict) -> dict:
        """广播信号"""
        if self.protocol:
            return self.protocol.broadcast(message)
        return {}

    def sense(self, target: str, sense_type: str = "system") -> Optional[dict]:
        """分布式感知"""
        if self.protocol:
            return self.protocol.sense(target, sense_type)
        return None

    def sense_all(self) -> Dict[str, dict]:
        """感知所有节点"""
        results = {}
        if not self.layer:
            return results

        for name in self.layer.nodes.keys():
            if name != "brain":
                result = self.sense(name, "system")
                if result and result.get("status") == "ok":
                    raw = result.get("data", result.get("raw", ""))
                    if isinstance(raw, str):
                        # 提取JSON（跳过节点服务的print输出）
                        import re
                        # 找第一个 { 到最后一个 }
                        match = re.search(r'\{.*\}', raw, re.DOTALL)
                        if match:
                            try:
                                parsed = json.loads(match.group())
                                results[name] = parsed
                            except json.JSONDecodeError:
                                results[name] = {"raw": raw}
                        else:
                            results[name] = {"raw": raw}
                    elif isinstance(raw, dict):
                        results[name] = raw
        return results

    def register_reflex(self, condition: str, action: dict, target: str = "singapore") -> dict:
        """注册反射弧"""
        if self.protocol:
            return self.protocol.register_reflex(target, condition, action)
        return {"status": "error", "message": "protocol not available"}

    def heartbeat_check(self) -> dict:
        """心跳检测"""
        if self.heartbeat:
            return self.heartbeat.beat()
        return {}

    def print_status(self):
        """打印状态"""
        status = self.status()
        print("\n🧠 神经层系统状态")
        print(f"时间: {status['timestamp']}")
        print(f"\n节点数: {len(status['nodes'])}")

        for name, info in status["nodes"].items():
            ip = info.get("vpn_ip", info.get("ip", "?"))
            st = info.get("status", "?")
            role = info.get("role", "?")
            emoji = "✅" if st == "online" else "❌"
            print(f"  {emoji} {name} ({ip}) [{role}]")

        print(f"\n反射弧数: {len(status['reflex_arcs'])}")
        for arc in status["reflex_arcs"]:
            print(f"  • {arc['name']}: {arc['condition']}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="神经层总控")
    parser.add_argument("--status", "-s", action="store_true", help="查看状态")
    parser.add_argument("--ping", "-p", metavar="NODE", help="Ping节点")
    parser.add_argument("--sense", "-S", metavar="NODE", help="感知节点")
    parser.add_argument("--sense-all", "-A", action="store_true", help="感知所有节点")
    parser.add_argument("--broadcast", "-b", metavar="MSG", help="广播消息")
    parser.add_argument("--heartbeat", action="store_true", help="心跳检测")
    parser.add_argument("--test", "-t", action="store_true", help="完整测试")
    args = parser.parse_args()

    neural = NeuralSystem()

    if args.status or (not args.ping and not args.sense and not args.sense_all and not args.broadcast and not args.heartbeat and not args.test):
        neural.print_status()

    elif args.ping:
        result = neural.signal(args.ping, "ping", {})
        print(f"Ping {args.ping}: {result}")

    elif args.sense:
        result = neural.sense(args.sense, "system")
        print(f"Sense {args.sense}: {result}")

    elif args.sense_all:
        print("\n📡 感知所有节点:")
        results = neural.sense_all()
        for node, data in results.items():
            print(f"  {node}: {data}")

    elif args.broadcast:
        results = neural.broadcast({"type": "broadcast", "message": args.broadcast})
        print(f"广播结果: {results}")

    elif args.heartbeat:
        result = neural.heartbeat_check()
        print(f"心跳检测: {result}")

    elif args.test:
        print("\n🧠 神经层完整测试")
        print("="*50)

        # 状态
        neural.print_status()
        print()

        # 心跳
        print("📡 心跳检测:")
        hb = neural.heartbeat_check()
        for node, status in hb.items():
            print(f"  {node}: {status['status']}")
        print()

        # 感知
        print("💾 分布式感知:")
        results = neural.sense_all()
        for node, data in results.items():
            cpu = data.get("cpu", "?")
            mem = data.get("memory", "?")
            disk = data.get("disk", "?")
            print(f"  {node}: CPU {cpu} | 内存 {mem} | 磁盘 {disk}")
        print()

        print("✅ 测试完成")


if __name__ == "__main__":
    main()