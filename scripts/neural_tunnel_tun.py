#!/usr/bin/env python3
"""
neural_tunnel_tun.py - TUN虚拟网卡模块

将Neural Tunnel接入系统网络层
让隧道作为虚拟网卡，系统所有流量自动路由到隧道

用法:
    hub = TunnelHubTUN(port=9527, tun_name="ntrp0", tun_ip="10.200.0.1")
    hub.start()
    
    node = TunnelNodeTUN(node_id="node1", hub_addr=(...), tun_ip="10.200.0.2")
    node.start()

Author: OpenClaw AI Agent
Version: 1.0.0
"""

import os
import sys
import stat
import struct
import threading
import socket
import logging
import subprocess
import fcntl
import select
from dataclasses import dataclass, field
from typing import Optional, Callable
from pathlib import Path

# ============== 复用 neural_tunnel.py 的核心 ==============

WORKSPACE = Path("/root/.openclaw/workspace")
TUNNEL_CORE = WORKSPACE / "scripts" / "neural_tunnel.py"

# 动态加载neural_tunnel（避免循环import）
_spec = None
_neural_tunnel = None

def _load_neural_tunnel():
    global _neural_tunnel, _spec
    if _neural_tunnel is None:
        import importlib.util
        _spec = importlib.util.spec_from_file_location("neural_tunnel", TUNNEL_CORE)
        _neural_tunnel = importlib.util.module_from_spec(_spec)
        sys.modules["neural_tunnel"] = _neural_tunnel
        _spec.loader.exec_module(_neural_tunnel)
    return _neural_tunnel


# ============== 日志 ==============

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("NeuralTunnelTUN")


# ============== TUN设备 ==============

# TUN设备ioctl定义
TUNSETIFF = 0x400454ca
TUNSETPERSIST = 0x400454cb
TUNSETOWNER = 0x400454cc
IFF_TUN = 0x0001
IFF_TAP = 0x0002
IFF_NO_PI = 0x1000  # 不带PI（package info）前缀
IFF_ONE_QUEUE = 0x2000


class TUNDevice:
    """
    TUN虚拟网卡封装

    读取：从TUN设备读取IP包（系统→隧道）
    写入：向TUN设备写入IP包（隧道→系统）
    """

    def __init__(self, name: str = "ntrp%d", ip_addr: str = None, netmask: str = "255.255.255.0"):
        self.name = name
        self.ip_addr = ip_addr
        self.netmask = netmask
        self.fd: Optional[int] = None
        self.tun_file = None
        self.running = False
        self.thread_read: Optional[threading.Thread] = None
        self._on_packet: Optional[Callable[[bytes], None]] = None

    def open(self, persist: bool = False) -> bool:
        """打开TUN设备"""
        try:
            # 打开/dev/net/tun
            self.tun_file = open("/dev/net/tun", "r+b", buffering=0)
        except PermissionError:
            logger.error("❌ 需要root权限创建TUN设备")
            return False
        except FileNotFoundError:
            logger.error("❌ /dev/net/tun 不存在")
            return False

        # 设置TUN属性
        iface_name = self.name.encode() if isinstance(self.name, str) else self.name
        # struct ifreq: name[16 bytes] + flags[2 bytes]
        ifr = iface_name + b'\x00' * (16 - len(iface_name)) + struct.pack("HH", IFF_TUN | IFF_NO_PI, 0)

        try:
            fcntl.ioctl(self.tun_file.fileno(), TUNSETIFF, ifr)
        except IOError as e:
            logger.error(f"❌ ioctl设置TUN失败: {e}")
            self.tun_file.close()
            return False

        # 获取实际设备名
        actual_name = ifr[:16].rstrip(b'\x00').decode()
        self.name = actual_name
        logger.info(f"🔧 TUN设备已创建: {actual_name}")

        if persist:
            try:
                fcntl.ioctl(self.tun_file.fileno(), TUNSETPERSIST, 1)
                logger.info(f"  持久化TUN设备")
            except IOError:
                pass

        # 配置IP（如果指定）
        if self.ip_addr:
            self._configure_ip()

        self.running = True
        return True

    def _configure_ip(self):
        """配置TUN设备IP"""
        try:
            # ip addr add
            subprocess.run(
                ["ip", "addr", "add", f"{self.ip_addr}/24", "dev", self.name],
                check=True, capture_output=True
            )
            # ip link set up
            subprocess.run(
                ["ip", "link", "set", self.name, "up"],
                check=True, capture_output=True
            )
            logger.info(f"  IP配置: {self.ip_addr}/24")
        except subprocess.CalledProcessError as e:
            logger.warning(f"  IP配置失败: {e.stderr.decode() if e.stderr else e}")

    def close(self):
        """关闭TUN设备"""
        self.running = False
        if self.tun_file:
            try:
                self.tun_file.close()
            except:
                pass
        logger.info(f"🛑 TUN设备 {self.name} 已关闭")

    def set_on_packet(self, callback: Callable[[bytes], None]):
        """设置数据包回调（从TUN读取时调用）"""
        self._on_packet = callback

    def start_reading(self):
        """启动读取线程"""
        self.thread_read = threading.Thread(target=self._read_loop, daemon=True)
        self.thread_read.start()

    def _read_loop(self):
        """从TUN设备读取IP包"""
        logger.info(f"📖 TUN读取线程启动 ({self.name})")
        while self.running:
            try:
                # 使用select监听TUN文件描述符
                ready, _, _ = select.select([self.tun_file], [], [], 0.5)
                if not ready:
                    continue

                # 读取数据（不带PI前缀）
                packet = self.tun_file.read(65535)
                if not packet:
                    continue

                # 解析IP头（判断是IPv4还是IPv6）
                if len(packet) < 20:
                    continue

                version = (packet[0] >> 4) & 0xF
                if version == 4:
                    total_len = struct.unpack("!H", packet[2:4])[0]
                elif version == 6:
                    total_len = struct.unpack("!H", packet[4:6])[0]
                else:
                    logger.warning(f"未知IP版本: {version}")
                    continue

                logger.debug(f"📤 TUN收到IP包: {version} {total_len} bytes")

                if self._on_packet:
                    self._on_packet(packet)

            except Exception as e:
                if self.running:
                    logger.error(f"TUN读取错误: {e}")

        logger.info(f"📖 TUN读取线程退出")

    def write(self, packet: bytes) -> bool:
        """向TUN设备写入IP包"""
        if not self.tun_file:
            return False
        try:
            self.tun_file.write(packet)
            return True
        except Exception as e:
            logger.error(f"TUN写入失败: {e}")
            return False

    @staticmethod
    def cleanup(name: str):
        """清理TUN设备（需要root）"""
        try:
            subprocess.run(["ip", "link", "del", name], check=True, capture_output=True)
            logger.info(f"🧹 TUN设备已清理: {name}")
        except subprocess.CalledProcessError:
            pass


# ============== IP包解析 ==============

def parse_ip_packet(packet: bytes) -> dict:
    """解析IP包，返回头部信息"""
    if len(packet) < 20:
        return {}

    version = (packet[0] >> 4) & 0xF
    if version == 4:
        header_len = (packet[0] & 0xF) * 4
        src_ip = socket.inet_ntoa(packet[12:16])
        dst_ip = socket.inet_ntoa(packet[16:20])
        proto = packet[9]
    elif version == 6:
        header_len = 40
        src_ip = socket.inet_ntop(socket.AF_INET6, packet[8:24])
        dst_ip = socket.inet_ntop(socket.AF_INET6, packet[24:40])
        proto = packet[6]
    else:
        return {}

    return {
        "version": version,
        "header_len": header_len,
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "protocol": proto,
        "payload": packet[header_len:],
    }


def is_private_ip(ip: str) -> bool:
    """判断是否为私有IP（简化版）"""
    if ip.startswith("10."):
        return True
    if ip.startswith("172."):
        second = int(ip.split(".")[1])
        if 16 <= second <= 31:
            return True
    if ip.startswith("192.168."):
        return True
    if ip.startswith("127."):
        return True
    return False


# ============== TunnelHubTUN ==============

class TunnelHubTUN:
    """
    带TUN接口的中枢

    功能：
    - 监听UDP端口，处理隧道握手和加密数据
    - TUN虚拟网卡，劫持指定网段的流量
    - 自动路由：收到TUN数据 → 发送到对应节点
    - 自动路由：收到节点数据 → 写入TUN（交给系统路由）
    """

    def __init__(self, listen_port: int = 9527,
                 tun_name: str = "ntrp0",
                 tun_ip: str = "10.200.0.1",
                 tun_netmask: str = "255.255.255.0",
                 route_cidr: str = "10.200.0.0/24",
                 static_private_bytes: bytes = None):
        nt = _load_neural_tunnel()
        self._nt = nt

        # 核心隧道
        self.hub = nt.TunnelHub(listen_port=listen_port,
                                static_private_bytes=static_private_bytes)

        # TUN设备
        self.tun = TUNDevice(name=tun_name, ip_addr=tun_ip, netmask=tun_netmask)
        self.route_cidr = route_cidr
        self.tun_ip = tun_ip

        # 路由表：目标IP → 节点ID
        self.route_table: dict = {}

        # 回调
        self.on_route: Optional[Callable[[str, bytes], None]] = None

    def start(self) -> bool:
        """启动Hub + TUN"""
        # 打开TUN
        if not self.tun.open(persist=True):
            return False

        # 添加到路由表（劫持目标网段）
        self._add_route()

        # 设置TUN读取回调
        self.tun.set_on_packet(self._on_tun_packet)
        self.tun.start_reading()

        # 设置Hub收到数据的回调
        self.hub.on_node_message = self._on_node_message
        self.hub.on_node_connect = self._on_node_connect

        # 启动Hub
        self.hub.start()

        logger.info(f"🌀 TunnelHubTUN 启动")
        logger.info(f"  监听: UDP {self.hub.port}")
        logger.info(f"  TUN: {self.tun.name} {self.tun_ip}/24")
        logger.info(f"  路由: {self.route_cidr} → 隧道")
        return True

    def stop(self):
        """停止Hub + TUN"""
        self._remove_route()
        self.hub.stop()
        self.tun.close()
        logger.info("🛑 TunnelHubTUN 已停止")

    def _add_route(self):
        """添加路由规则（劫持流量）"""
        try:
            # 先删除旧路由
            subprocess.run(
                ["ip", "route", "del", self.route_cidr],
                check=False, capture_output=True
            )
            # 添加新路由到TUN设备
            subprocess.run(
                ["ip", "route", "add", self.route_cidr, "dev", self.tun.name],
                check=True, capture_output=True
            )
            logger.info(f"  路由已添加: {self.route_cidr} dev {self.tun.name}")
        except subprocess.CalledProcessError as e:
            logger.warning(f"  路由添加失败: {e}")

    def _remove_route(self):
        """移除路由规则"""
        try:
            subprocess.run(
                ["ip", "route", "del", self.route_cidr],
                check=True, capture_output=True
            )
        except:
            pass

    def _on_tun_packet(self, packet: bytes):
        """TUN收到系统数据包（需要发送到远程节点）"""
        parsed = parse_ip_packet(packet)
        if not parsed:
            return

        dst_ip = parsed["dst_ip"]
        logger.debug(f"📤 TUN收到: {parsed['src_ip']} → {dst_ip}")

        # 查找路由（目标IP → 节点）
        if dst_ip in self.route_table:
            node_id = self.route_table[dst_ip]
            self.hub.send_to_node(node_id, packet)
        else:
            # 广播到所有节点（或者丢弃）
            logger.debug(f"  无路由，广播到所有节点")
            self.hub.broadcast(packet)

    def _on_node_message(self, node_id: str, data: bytes):
        """Hub收到节点数据（需要写入TUN）"""
        parsed = parse_ip_packet(data)
        if not parsed:
            return

        logger.debug(f"📥 节点{node_id}收到: {parsed['src_ip']} → {parsed['dst_ip']}")

        # 写入TUN（交给系统路由栈）
        self.tun.write(data)

        # 回调
        if self.on_route:
            self.on_route(node_id, data)

    def _on_node_connect(self, node_id: str):
        """节点连接，分配IP"""
        # 分配IP（从.2开始）
        parts = self.tun_ip.rsplit(".", 1)
        base = parts[0]
        idx = 2 + len(self.route_table)  # .2, .3, ...
        assigned_ip = f"{base}.{idx}"

        self.route_table[assigned_ip] = node_id
        logger.info(f"  节点{node_id}分配IP: {assigned_ip}")

        # TODO: 通知节点自己的IP（通过握手响应）

    def send_to_node(self, node_id: str, data: bytes) -> bool:
        """发送数据到节点"""
        return self.hub.send_to_node(node_id, data)

    def broadcast(self, data: bytes) -> int:
        """广播到所有节点"""
        return self.hub.broadcast(data)

    def get_stats(self) -> dict:
        """获取统计"""
        return {
            "hub": self.hub.get_stats(),
            "tun": self.tun.name,
            "routes": len(self.route_table),
        }


# ============== TunnelNodeTUN ==============

class TunnelNodeTUN:
    """
    带TUN接口的节点

    功能：
    - 连接中枢隧道
    - TUN虚拟网卡，所有应用流量进入隧道
    - 隧道数据写入TUN，应用无感知
    """

    def __init__(self, node_id: str,
                 hub_addr: tuple,
                 tun_ip: str = "10.200.0.2",
                 tun_netmask: str = "255.255.255.0",
                 default_gateway: str = "10.200.0.1",
                 listen_port: int = 0,
                 static_private_bytes: bytes = None):
        nt = _load_neural_tunnel()
        self._nt = nt

        # 核心隧道
        self.node = nt.TunnelNode(
            node_id=node_id,
            hub_addr=hub_addr,
            listen_port=listen_port
        )

        # TUN设备
        self.tun = TUNDevice(name="ntrc%d", ip_addr=tun_ip, netmask=tun_netmask)
        self.default_gateway = default_gateway

        # 回调
        self.on_route: Optional[Callable[[bytes], None]] = None

    def start(self) -> bool:
        """启动Node + TUN"""
        # 打开TUN
        if not self.tun.open(persist=False):
            return False

        # 设置默认路由（所有流量走隧道）
        self._add_default_route()

        # 设置TUN读取回调
        self.tun.set_on_packet(self._on_tun_packet)
        self.tun.start_reading()

        # 设置Hub收到数据的回调
        self.node.on_hub_message = self._on_hub_message
        self.node.on_connect = self._on_node_connect
        self.node.on_disconnect = self._on_node_disconnect

        # 连接Hub
        if not self.node.start():
            self.tun.close()
            self._remove_default_route()
            return False

        logger.info(f"📡 TunnelNodeTUN {self.node.node_id} 启动")
        logger.info(f"  TUN: {self.tun.name} {self.tun.ip_addr}/24")
        logger.info(f"  网关: {self.default_gateway}")
        return True

    def stop(self):
        """停止Node + TUN"""
        self.node.stop()
        self._remove_default_route()
        self.tun.close()
        logger.info(f"🛑 TunnelNodeTUN {self.node.node_id} 已停止")

    def _add_default_route(self):
        """添加默认路由（所有流量走隧道）"""
        try:
            # 添加到Hub IP的路由（不走隧道，否则死循环）
            subprocess.run(
                ["ip", "route", "add", self.default_gateway + "/32", "via", "0.0.0.0", "dev", self.tun.name],
                check=False, capture_output=True
            )
            # 添加默认网关路由
            subprocess.run(
                ["ip", "route", "add", "default", "via", self.default_gateway, "dev", self.tun.name],
                check=True, capture_output=True
            )
            logger.info(f"  默认路由已添加: via {self.default_gateway}")
        except subprocess.CalledProcessError as e:
            logger.warning(f"  路由添加失败: {e}")

    def _remove_default_route(self):
        """移除默认路由"""
        try:
            subprocess.run(
                ["ip", "route", "del", "default"],
                check=True, capture_output=True
            )
        except:
            pass

    def _on_tun_packet(self, packet: bytes):
        """TUN收到应用数据包，发送到Hub"""
        parsed = parse_ip_packet(packet)
        if not parsed:
            return

        # 检查目标IP
        dst_ip = parsed["dst_ip"]

        # 跳过到Hub本身的连接（避免死循环）
        hub_host = self.node.hub_addr[0]
        if dst_ip == hub_host or dst_ip == self.default_gateway:
            logger.debug(f"  跳过Hub自身: {dst_ip}")
            return

        logger.debug(f"📤 TUN→Hub: {parsed['src_ip']} → {dst_ip}")

        # 通过隧道发送到Hub
        self.node.send(packet)

        if self.on_route:
            self.on_route(packet)

    def _on_hub_message(self, data: bytes):
        """Hub收到中枢数据，写入TUN"""
        parsed = parse_ip_packet(data)
        if not parsed:
            return

        logger.debug(f"📥 Hub→TUN: {parsed['src_ip']} → {parsed['dst_ip']}")

        # 写入TUN（交给系统路由栈处理）
        self.tun.write(data)

        if self.on_route:
            self.on_route(data)

    def _on_node_connect(self):
        """连接成功"""
        logger.info(f"✅ Node {self.node.node_id} 已连接")

    def _on_node_disconnect(self):
        """连接断开"""
        logger.warning(f"🔌 Node {self.node.node_id} 已断开")

    def send(self, data: bytes) -> bool:
        """发送数据到Hub"""
        return self.node.send(data)

    def is_connected(self) -> bool:
        return self.node.is_connected()


# ============== 演示 ==============

def demo_hub():
    """Hub+TUN演示"""
    print("\n🌀 TunnelHubTUN 演示")
    print("="*50)

    hub = TunnelHubTUN(
        listen_port=19527,
        tun_name="ntrp0",
        tun_ip="10.200.0.1",
        route_cidr="10.200.0.0/24"
    )

    if not hub.start():
        print("❌ 启动失败（需要root）")
        return

    print("Hub+TUN运行中...")
    print("  Ctrl+C 停止\n")

    try:
        while hub.hub.running:
            time.sleep(1)
            stats = hub.get_stats()
            print(f"\r  会话: {stats['hub']['sessions']} | 路由: {stats['routes']}  ", end="", flush=True)
    except KeyboardInterrupt:
        print("\n")
        hub.stop()


def demo_node():
    """Node+TUN演示"""
    print("\n📡 TunnelNodeTUN 演示")
    print("="*50)

    node = TunnelNodeTUN(
        node_id="test_node",
        hub_addr=("127.0.0.1", 19527),
        tun_ip="10.200.0.2"
    )

    if not node.start():
        print("❌ 启动失败（需要root）")
        return

    print("Node+TUN运行中...")
    print("  Ctrl+C 停止\n")

    try:
        while node.is_connected():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n")
        node.stop()


if __name__ == "__main__":
    import time

    if len(sys.argv) < 2:
        print("用法: neural_tunnel_tun.py [hub|node]")
        print("  hub   - 启动中枢TUN（需要root）")
        print("  node  - 启动节点TUN（需要root）")
        sys.exit(1)

    if sys.argv[1] == "hub":
        demo_hub()
    elif sys.argv[1] == "node":
        demo_node()
    else:
        print(f"未知模式: {sys.argv[1]}")
        sys.exit(1)
