#!/usr/bin/env python3
"""
neural_layer.py - 神经层核心
用 WireGuard VPN 作为神经纤维，实现节点间信号传输

架构：
  主Agent（中枢/脑） ←→ 节点A（新加坡/手） ←→ 节点B（未来扩展）
  
神经纤维：WireGuard VPN (10.0.0.x)
信号协议：SSH over VPN + JSON命令
"""

import os
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Callable

WORKSPACE = Path("/root/.openclaw/workspace")
NODES_FILE = WORKSPACE / "neural_nodes.json"
HEARTBEAT_FILE = WORKSPACE / "neural_heartbeat.json"

SSH_CMD = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", "/root/.ssh/id_ed25519"]

# 神经层解密与审计模块（可选，未安装则跳过）
_neural_decryptor = None
try:
    from neural_decryptor import NeuralDecryptor
    _neural_decryptor = NeuralDecryptor()
    print(f"[NeuralLayer] ✅ 解密与审计模块已加载")
except ImportError:
    print(f"[NeuralLayer] ℹ️ 解密模块未安装，跳过审计（可安装 neural_decryptor.py 启用）")


class NeuralNode:
    """神经节点"""

    def __init__(self, name: str, vpn_ip: str, public_ip: str = "", public_key: str = "", role: str = "worker"):
        self.name = name
        self.vpn_ip = vpn_ip       # 10.0.0.x (VPN内网)
        self.public_ip = public_ip  # 公网IP（SSH备用）
        self.public_key = public_key
        self.role = role  # brain / worker / sensor
        self.last_heartbeat = None
        self.status = "offline"
        self.capabilities = []
        self._ssh_key = "/root/.ssh/id_ed25519"

    @property
    def ip(self):
        """优先用VPN IP，如果不通则fallback到公网IP"""
        return self.vpn_ip

    def to_dict(self):
        return {
            "name": self.name,
            "vpn_ip": self.vpn_ip,
            "public_ip": self.public_ip,
            "public_key": self.public_key,
            "role": self.role,
            "last_heartbeat": self.last_heartbeat,
            "status": self.status,
            "capabilities": self.capabilities,
        }

    @staticmethod
    def from_dict(d: dict):
        node = NeuralNode(d["name"], d["vpn_ip"], d.get("public_ip", ""), d.get("public_key", ""), d.get("role", "worker"))
        node.last_heartbeat = d.get("last_heartbeat")
        node.status = d.get("status", "offline")
        node.capabilities = d.get("capabilities", [])
        return node


class NeuralLayer:
    """
    神经层：管理所有节点和信号传输

    用法：
        neural = NeuralLayer()
        neural.register_node("singapore", "10.0.0.2", vpn_ip="178.128.52.85", role="worker")
        neural.signal("singapore", {"type": "exec", "cmd": "ls /root"})
        neural.broadcast({"type": "ping"})
    """

    def __init__(self):
        self.nodes: Dict[str, NeuralNode] = {}
        self.self_ip = "10.0.0.1"  # 主服务器是中枢
        self.self_name = "brain"
        self._load_nodes()

    def _load_nodes(self):
        """从文件加载节点注册表"""
        if NODES_FILE.exists():
            try:
                data = json.loads(NODES_FILE.read_text())
                for d in data.get("nodes", []):
                    node = NeuralNode.from_dict(d)
                    self.nodes[node.name] = node
            except Exception as e:
                print(f"[NeuralLayer] 节点加载失败: {e}")

    def _save_nodes(self):
        """保存节点注册表"""
        data = {"nodes": [n.to_dict() for n in self.nodes.values()]}
        NODES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def register_node(self, name: str, vpn_ip: str, public_ip: str = "", public_key: str = "", role: str = "worker") -> NeuralNode:
        """注册新节点"""
        node = NeuralNode(name, vpn_ip, public_ip, public_key, role)
        self.nodes[name] = node
        self._save_nodes()
        print(f"[NeuralLayer] ✅ 注册节点: {name} (VPN:{vpn_ip} / 公网:{public_ip}) [{role}]")
        return node

    def discover_local_node(self) -> NeuralNode:
        """自动发现本机节点（中枢）"""
        node = NeuralNode("brain", self.self_ip, role="brain")
        node.status = "online"
        node.last_heartbeat = datetime.now().isoformat()
        node.capabilities = ["orchestrate", "decide", "remember", "communicate"]
        self.nodes["brain"] = node
        self._update_self_heartbeat()
        return node

    def _update_self_heartbeat(self):
        """更新本机心跳"""
        hb = {
            "node": "brain",
            "ip": self.self_ip,
            "timestamp": datetime.now().isoformat(),
            "status": "online",
        }
        HEARTBEAT_FILE.write_text(json.dumps(hb, indent=2))

    def _resolve_ip(self, node: NeuralNode) -> str:
        """解析最佳IP：优先VPN，不通则公网"""
        # 先试VPN内网
        result = subprocess.run(["ping", "-c", "1", "-W", "1", node.vpn_ip], capture_output=True)
        if result.returncode == 0:
            return node.vpn_ip
        # Fallback到公网IP
        if node.public_ip:
            return node.public_ip
        return node.vpn_ip

    def signal(self, target: str, message: dict, timeout: int = 30) -> Optional[dict]:
        """
        神经冲动：向目标节点发送信号

        Args:
            target: 节点名称（singapore/brain等）
            message: 信号内容 {"type": "...", ...}
            timeout: 超时秒数

        Returns:
            响应数据或None
        """
        if target not in self.nodes:
            print(f"[NeuralLayer] ❌ 未知节点: {target}")
            return None

        node = self.nodes[target]
        resolved_ip = self._resolve_ip(node)

        # 构建信号JSON
        signal = {
            "from": "brain",
            "to": target,
            "timestamp": datetime.now().isoformat(),
            **message
        }

        # 通过SSH发送信号，节点端执行neural_node_service.py解析
        cmd = SSH_CMD + [
            f"root@{resolved_ip}",
            f"python3 /root/.openclaw/workspace/neural_node_service.py --once <<'EOF'\n{json.dumps(signal)}\nEOF"
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            stdout = result.stdout.strip()

            # ========== 神经层安全审计（入口）==========
            audit_passed = True
            audit_blocked = False
            if _neural_decryptor:
                # 尝试解析JSON
                parsed = None
                for line in stdout.split('\n'):
                    line = line.strip()
                    if line.startswith('{'):
                        try:
                            parsed = json.loads(line)
                            break
                        except json.JSONDecodeError:
                            continue

                if parsed:
                    is_safe, audited = _neural_decryptor.process_incoming(parsed, target)
                    if not is_safe:
                        print(f"[NeuralLayer] 🚫 信号被审计拦截: {target} - {audited.get('_neural_audit', {}).get('reason')}")
                        audit_blocked = True
                        node.last_heartbeat = datetime.now().isoformat()
                        node.status = "online"
                        self._save_nodes()
                        return {"status": "blocked", "audit": audited.get('_neural_audit', {})}
                else:
                    # 无法解析，检查原始文本
                    _, audited = _neural_decryptor.process_incoming({"raw": stdout[:500]}, target)
                    if audited.get('_neural_audit', {}).get('status') == 'blocked':
                        print(f"[NeuralLayer] 🚫 原始输出被审计拦截")
                        audit_blocked = True
                        return {"status": "blocked", "audit": audited.get('_neural_audit', {})}
            # ========== 审计结束 =========#

            # 尝试解析返回的JSON
            if stdout.startswith("{"):
                try:
                    parsed = json.loads(stdout)
                    node.last_heartbeat = datetime.now().isoformat()
                    node.status = "online"
                    self._save_nodes()
                    return {"status": "ok", "data": parsed}
                except json.JSONDecodeError:
                    pass
            if result.returncode == 0:
                node.last_heartbeat = datetime.now().isoformat()
                node.status = "online"
                self._save_nodes()
                return {"status": "ok", "raw": stdout}
            else:
                print(f"[NeuralLayer] ❌ 信号发送失败: {result.stderr[:100]}")
                return {"status": "error", "message": result.stderr[:200]}
        except subprocess.TimeoutExpired:
            print(f"[NeuralLayer] ⏱️ 信号超时: {target}")
            node.status = "timeout"
            return {"status": "timeout"}
        except Exception as e:
            print(f"[NeuralLayer] ❌ 信号异常: {e}")
            return {"status": "error", "message": str(e)}

    def broadcast(self, message: dict) -> Dict[str, dict]:
        results = {}
        for name in list(self.nodes.keys()):
            if name != "brain":  # 不给自己发
                results[name] = self.signal(name, message)
        return results

    def reflex(self, target: str, condition: str, action: dict):
        """
        条件反射：节点满足条件时自动触发动作（不经过中枢）

        例如：新加坡节点检测到异常 → 自动执行预设动作
        """
        reflex_script = f"""
import json, subprocess, sys

# 条件：{condition}
# 动作：{json.dumps(action)}

# 这里可以是更复杂的条件判断逻辑
# 通过 signal回传结果
"""
        # 将反射弧注册到目标节点
        reflex_msg = {
            "type": "register_reflex",
            "condition": condition,
            "action": action,
            "script": reflex_script,
        }
        return self.signal(target, reflex_msg)

    def get_status(self) -> dict:
        """获取所有节点状态"""
        status = {"brain": {"ip": self.self_ip, "status": "online"}}
        for name, node in self.nodes.items():
            if name != "brain":
                status[name] = {
                    "vpn_ip": node.vpn_ip,
                    "public_ip": node.public_ip,
                    "status": node.status,
                    "role": node.role,
                    "last_heartbeat": node.last_heartbeat,
                }
        return status

    def ping_all(self) -> Dict[str, bool]:
        """测试所有节点连通性（VPN优先，公网兜底）"""
        results = {}
        for name, node in self.nodes.items():
            if name == "brain":
                results[name] = True
                continue
            # 先ping VPN IP
            result = subprocess.run(["ping", "-c", "1", "-W", "2", node.vpn_ip], capture_output=True)
            if result.returncode == 0:
                results[name] = True
                node.status = "online"
            elif node.public_ip:
                # VPN不通，ping公网IP
                result2 = subprocess.run(["ping", "-c", "1", "-W", "2", node.public_ip], capture_output=True)
                results[name] = (result2.returncode == 0)
                node.status = "online" if results[name] else "offline"
            else:
                results[name] = False
                node.status = "offline"
        self._save_nodes()
        return results


def init_neural_layer():
    """初始化神经层"""
    neural = NeuralLayer()

    # 自动发现本机节点
    neural.discover_local_node()

    # 注册已知节点（新加坡：VPN IP + 公网IP）
    neural.register_node("singapore", "10.0.0.2", public_ip="178.128.52.85", role="worker")

    # 测试连通性（VPN优先，公网兜底）
    print("\n🧠 神经层初始化")
    print(f"节点数: {len(neural.nodes)}")
    print(f"中枢IP: {neural.self_ip}")

    # Ping测试（VPN优先，公网备用）
    print("\n📡 连通性测试:")
    ping_results = neural.ping_all()
    for node, alive in ping_results.items():
        status = "✅" if alive else "❌"
        print(f"  {status} {node}")

    neural._save_nodes()
    return neural


if __name__ == "__main__":
    neural = init_neural_layer()
    print("\n📊 节点状态:")
    import pprint
    pprint.pprint(neural.get_status())