#!/usr/bin/env python3
"""
neural_protocol.py - 神经冲动协议定义

四种信号类型：
1. signal()  - 点对点神经冲动（中枢→节点）
2. sense()   - 分布式感知（节点→中枢汇报）
3. reflex()  - 条件反射（节点自主反应）
4. broadcast() - 广播神经冲动（中枢→所有节点）
"""

import json
import time
from datetime import datetime
from typing import Optional, Callable
from pathlib import Path

SIGNALS_DIR = Path("/root/.openclaw/workspace/neural_signals")


class NeuralSignal:
    """神经冲动信号"""

    TYPES = {
        "ping":        "连接测试",
        "pong":        "连接响应",
        "exec":        "执行命令",
        "result":      "执行结果",
        "sense":       "感知请求",
        "sense_data":  "感知数据",
        "reflex":      "条件反射",
        "broadcast":   "广播信号",
        "status":      "状态查询",
        "status_report": "状态报告",
    }

    def __init__(self, signal_type: str, from_node: str, to_node: str,
                 payload: dict = None, ttl: int = 30):
        self.signal_type = signal_type
        self.from_node = from_node
        self.to_node = to_node
        self.payload = payload or {}
        self.ttl = ttl  # 生存时间（秒）
        self.timestamp = datetime.now().isoformat()
        self.signal_id = f"{from_node}_{to_node}_{int(time.time()*1000)}"

    def to_dict(self):
        return {
            "signal_id": self.signal_id,
            "type": self.signal_type,
            "from": self.from_node,
            "to": self.to_node,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "ttl": self.ttl,
        }

    def is_expired(self) -> bool:
        """检查是否过期"""
        created = datetime.fromisoformat(self.timestamp)
        age = (datetime.now() - created).total_seconds()
        return age > self.ttl

    @staticmethod
    def from_dict(d: dict) -> "NeuralSignal":
        signal = NeuralSignal(
            d["type"], d["from"], d["to"], d.get("payload", {}), d.get("ttl", 30)
        )
        signal.signal_id = d.get("signal_id", "")
        signal.timestamp = d.get("timestamp", datetime.now().isoformat())
        return signal


class SignalProtocol:
    """
    信号传输协议

    协议定义：
    - signal()   中枢发命令给节点，节点执行后返回result
    - sense()    节点主动上报感知数据给中枢
    - reflex()   中枢向节点注册条件反射弧
    - broadcast() 中枢向所有节点广播相同信号
    """

    def __init__(self, neural_layer):
        self.neural = neural_layer
        self.signal_log = SIGNALS_DIR / "signal_history.jsonl"
        SIGNALS_DIR.mkdir(exist_ok=True)

    def _log_signal(self, signal: NeuralSignal, direction: str = "→"):
        """记录信号到日志"""
        entry = {
            "time": datetime.now().isoformat(),
            "direction": direction,
            **signal.to_dict()
        }
        try:
            with open(self.signal_log, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def signal(self, target: str, command: str, args: dict = None) -> Optional[dict]:
        """
        神经冲动（点对点）：中枢 → 节点

        Args:
            target: 节点名称
            command: 命令（exec/sense/status）
            args: 命令参数

        Returns:
            执行结果或None
        """
        args = args or {}
        msg = {
            "type": command,
            "args": args,
            "request_id": f"req_{int(time.time()*1000)}",
        }

        result = self.neural.signal(target, msg)
        signal = NeuralSignal("exec", "brain", target, msg)
        self._log_signal(signal, "→" if result and result.get("status") == "ok" else "←❌")
        return result

    def sense(self, target: str, sense_type: str, params: dict = None) -> Optional[dict]:
        """
        分布式感知：节点采集数据上报中枢

        Args:
            target: 节点名称
            sense_type: 感知类型（disk/cpu/network/processes）
            params: 感知参数

        Returns:
            感知数据
        """
        params = params or {}
        msg = {
            "type": "sense",
            "sense_type": sense_type,
            "params": params,
        }
        return self.neural.signal(target, msg)

    def broadcast(self, message: dict) -> dict:
        """
        广播神经冲动：中枢 → 所有节点

        Args:
            message: 广播内容

        Returns:
            各节点响应结果
        """
        results = {}
        for node_name in self.neural.nodes.keys():
            if node_name != "brain":
                results[node_name] = self.neural.signal(node_name, message)
        signal = NeuralSignal("broadcast", "brain", "all", message)
        self._log_signal(signal, "→")
        return results

    def register_reflex(self, target: str, condition: str, action: dict) -> Optional[dict]:
        """
        注册条件反射弧：中枢 → 节点

        节点满足condition时自动触发action，不经过中枢

        Args:
            target: 节点名称
            condition: 条件描述（字符串）
            action: 触发动作

        Returns:
            注册结果
        """
        msg = {
            "type": "register_reflex",
            "condition": condition,
            "action": action,
        }
        result = self.neural.signal(target, msg)
        signal = NeuralSignal("reflex", "brain", target, msg)
        self._log_signal(signal, "→")
        return result

    def get_signal_history(self, limit: int = 20) -> list:
        """获取信号历史"""
        if not self.signal_log.exists():
            return []
        try:
            lines = self.signal_log.read_text().strip().split("\n")
            entries = [json.loads(line) for line in lines if line]
            return entries[-limit:]
        except Exception:
            return []


# ============== 节点端信号处理 ==============

def node_handle_signal(signal_dict: dict) -> dict:
    """
    节点端信号处理器（部署到新加坡节点）

    接收从中枢发来的信号，处理后返回结果
    """
    signal = NeuralSignal.from_dict(signal_dict)
    if signal.is_expired():
        return {"status": "expired", "signal_id": signal.signal_id}

    signal_type = signal.signal_type
    payload = signal.payload

    if signal_type == "exec" or "type" in payload:
        # 执行命令
        cmd_type = payload.get("type", signal_type)
        args = payload.get("args", {})

        if cmd_type == "ping":
            return {"status": "ok", "pong": True, "node": "singapore", "timestamp": datetime.now().isoformat()}

        elif cmd_type == "exec":
            command = args.get("command", "")
            if command:
                import subprocess
                result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
                return {
                    "status": "ok",
                    "stdout": result.stdout[:1000],
                    "stderr": result.stderr[:200],
                    "returncode": result.returncode,
                }

        elif cmd_type == "sense":
            sense_type = payload.get("sense_type", "system")
            if sense_type == "system":
                import subprocess
                cpu = subprocess.run("cat /proc/loadavg 2>/dev/null | awk '{print $1,$2,$3}'", shell=True, capture_output=True, text=True)
                mem = subprocess.run("free -m | awk 'NR==2{print $3\"MB/\"$2\"MB\"}'", shell=True, capture_output=True, text=True)
                disk = subprocess.run("df -h / | tail -1 | awk '{print $5,$4}'", shell=True, capture_output=True, text=True)
                return {
                    "status": "ok",
                    "sense_type": "system",
                    "cpu_load": cpu.stdout.strip(),
                    "memory": mem.stdout.strip(),
                    "disk": disk.stdout.strip(),
                    "node": "singapore",
                }

        elif cmd_type == "register_reflex":
            # 注册条件反射弧
            condition = payload.get("condition", "")
            action = payload.get("action", {})
            reflex_file = Path("/root/.openclaw/workspace/neural_reflexes.json")
            reflexes = {}
            if reflex_file.exists():
                try:
                    reflexes = json.loads(reflex_file.read_text())
                except Exception:
                    pass
            reflexes[signal.signal_id] = {"condition": condition, "action": action, "created": datetime.now().isoformat()}
            reflex_file.write_text(json.dumps(reflexes, indent=2))
            return {"status": "ok", "reflex_registered": signal.signal_id}

        elif cmd_type == "status":
            return {
                "status": "ok",
                "node": "singapore",
                "role": "worker",
                "uptime": subprocess.run("uptime -p", shell=True, capture_output=True, text=True).stdout.strip(),
                "timestamp": datetime.now().isoformat(),
            }

    return {"status": "unknown_signal_type", "signal_id": signal.signal_id}


# ============== 快速测试 ==============

def test_protocol():
    """测试信号协议"""
    from neural_layer import init_neural_layer

    print("\n🧠 神经层协议测试")
    neural = init_neural_layer()
    protocol = SignalProtocol(neural)

    print("\n📡 测试 ping 信号...")
    result = protocol.signal("singapore", "ping", {})
    print(f"结果: {result}")

    print("\n📊 测试 status 信号...")
    result = protocol.signal("singapore", "status", {})
    print(f"状态: {result}")

    print("\n💾 测试 sense 系统信息...")
    result = protocol.sense("singapore", "system")
    print(f"感知: {result}")

    print("\n📨 信号历史:")
    for entry in protocol.get_signal_history(5):
        print(f"  {entry.get('direction', '?')} [{entry.get('type', '?')}] {entry.get('from', '?')} → {entry.get('to', '?')}")

    return neural, protocol


if __name__ == "__main__":
    test_protocol()