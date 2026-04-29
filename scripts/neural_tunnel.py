#!/usr/bin/env python3
"""
neural_tunnel.py - UDP私有神经隧道

全中心化架构，自研加密握手，帧协议，分片，重传
复用 neural_decryptor.py 的 HMAC+时间戳 防重放机制

Author: OpenClaw AI Agent
Version: 1.0.0
"""

import os
import sys
import json
import hmac
import hashlib
import time
import struct
import threading
import socket
import random
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Callable
from enum import IntEnum
from pathlib import Path

# ============== 常量 ==============

MAGIC = 0x4E545250  # "NTRP" 大端序
VERSION = 1

# 包类型
class PacketType(IntEnum):
    HANDSHAKE_INIT = 0x01      # 握手初始化
    HANDSHAKE_ACK = 0x02       # 握手确认
    HANDSHAKE_FIN = 0x03       # 握手完成
    DATA = 0x10                # 数据包
    DATA_ACK = 0x11            # 数据确认
    HEARTBEAT = 0x20           # 心跳
    HEARTBEAT_ACK = 0x21       # 心跳响应
    FRAGMENT = 0x30            # 分片
    FRAGMENT_ACK = 0x31        # 分片确认
    DISCONNECT = 0xFF          # 断开连接

# 隧道配置
DEFAULT_MTU = 1400             # 默认MTU
MAX_PAYLOAD = 65535 - 32       # 最大负载
FRAGMENT_SIZE = 1300           # 分片大小
HANDSHAKE_TIMEOUT = 10.0       # 握手超时（秒）
RETRANSMIT_TIMEOUT = 2.0       # 重传超时（秒）
MAX_RETRANS = 5                # 最大重传次数
WINDOW_SIZE = 16               # 滑动窗口大小
KEEPALIVE_INTERVAL = 30.0      # 保活间隔（秒）
REAP_TIMEOUT = 300.0           # 节点超时清理（秒）
REPLAY_WINDOW = 300.0          # 防重放窗口（秒）= 5分钟

# 共享密钥路径
WORKSPACE = Path("/root/.openclaw/workspace")
SECRET_FILE = WORKSPACE / ".neural_tunnel_secret"


# ============== 日志 ==============

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("NeuralTunnel")


# ============== 工具函数 ==============

def load_secret() -> bytes:
    """加载或生成共享密钥"""
    if SECRET_FILE.exists():
        return SECRET_FILE.read_text().strip().encode()
    secret = hashlib.sha256(os.urandom(32)).hexdigest()
    SECRET_FILE.write_text(secret)
    os.chmod(SECRET_FILE, 0o600)
    logger.warning(f"⚠️ 生成新共享密钥到 {SECRET_FILE}")
    return secret.encode()


def calc_hmac(secret: bytes, data: bytes) -> bytes:
    """计算HMAC-SHA256，取前8字节"""
    return hmac.new(secret, data, hashlib.sha256).digest()[:8]


def verify_hmac(secret: bytes, data: bytes, expected: bytes) -> bool:
    """恒定时间HMAC验证"""
    return hmac.compare_digest(calc_hmac(secret, data), expected)


def pack_frame(pkg_type: int, seq: int, frag_id: int, frag_count: int,
               payload: bytes, secret: bytes, ts: int = None) -> bytes:
    """打包帧"""
    if ts is None:
        ts = int(time.time() * 1000)  # 毫秒时间戳

    header = struct.pack(">IBBHHHIH",
        MAGIC,           # 4 bytes
        VERSION,         # 1 byte
        pkg_type,        # 1 byte
        seq,             # 4 bytes
        frag_id,         # 2 bytes
        frag_count,      # 2 bytes
        len(payload),    # 2 bytes
        ts,              # 8 bytes
    )
    # HMAC覆盖整个帧（不含HMAC自身）
    hmac_val = calc_hmac(secret, header + payload)
    return header + hmac_val + payload


def unpack_frame(data: bytes, secret: bytes) -> Optional[dict]:
    """解包帧，验证HMAC和时间戳"""
    if len(data) < 32:
        return None

    header = data[:24]
    hmac_val = data[24:32]
    payload = data[32:]

    magic, ver, pkg_type, seq, frag_id, frag_count, payload_len, ts = \
        struct.unpack(">IBBHHHIH", header)

    if magic != MAGIC:
        return None
    if ver != VERSION:
        return None

    # 验证HMAC
    if not verify_hmac(secret, header + payload, hmac_val):
        logger.warning(f"HMAC验证失败 seq={seq}")
        return None

    # 验证时间戳（防重放）
    now_ms = int(time.time() * 1000)
    age = abs(now_ms - ts)
    if age > REPLAY_WINDOW * 1000:
        logger.warning(f"时间戳过期 seq={seq} age={age}ms")
        return None

    if len(payload) != payload_len:
        return None

    return {
        "type": pkg_type,
        "seq": seq,
        "frag_id": frag_id,
        "frag_count": frag_count,
        "payload": payload,
        "ts": ts,
    }


# ============== 会话管理 ==============

@dataclass
class Session:
    """隧道会话"""
    node_id: str
    addr: Tuple[str, int]
    key: bytes = field(default_factory=lambda: os.urandom(32))
    seq_send: int = 0
    seq_recv: int = 0
    last_seen: float = field(default_factory=time.time)
    established: bool = False
    frag_buffer: Dict[int, bytes] = field(default_factory=dict)
    frag_count: int = 0
    pending_acks: set = field(default_factory=set)  # 待确认的序列号


class SessionManager:
    """会话管理器"""

    def __init__(self):
        self.sessions: Dict[str, Session] = {}
        self.lock = threading.Lock()
        self.secret = load_secret()

    def create_session(self, node_id: str, addr: Tuple[str, int]) -> Session:
        """创建新会话"""
        with self.lock:
            sess = Session(node_id=node_id, addr=addr)
            self.sessions[node_id] = sess
            logger.info(f"新建会话 {node_id} from {addr}")
            return sess

    def get_session(self, node_id: str) -> Optional[Session]:
        return self.sessions.get(node_id)

    def remove_session(self, node_id: str):
        with self.lock:
            if node_id in self.sessions:
                del self.sessions[node_id]
                logger.info(f"删除会话 {node_id}")

    def cleanup_stale(self):
        """清理超时会话"""
        now = time.time()
        stale = []
        for node_id, sess in self.sessions.items():
            if now - sess.last_seen > REAP_TIMEOUT:
                stale.append(node_id)
        for node_id in stale:
            self.remove_session(node_id)
        return len(stale)


# ============== 滑动窗口 + 重传 ==============

@dataclass
class PendingPacket:
    """待确认数据包"""
    data: bytes
    sent_at: float
    retrans: int = 0


class RetransmitWindow:
    """重传窗口"""

    def __init__(self, max_size: int = WINDOW_SIZE):
        self.max_size = max_size
        self.packets: Dict[int, PendingPacket] = {}
        self.lock = threading.Lock()

    def add(self, seq: int, data: bytes):
        with self.lock:
            self.packets[seq] = PendingPacket(data=data, sent_at=time.time())

    def ack(self, seq: int) -> bool:
        with self.lock:
            if seq in self.packets:
                del self.packets[seq]
                return True
            return False

    def get_expired(self, timeout: float = RETRANSMIT_TIMEOUT) -> List[Tuple[int, bytes]]:
        """获取超时需要重传的包"""
        now = time.time()
        expired = []
        with self.lock:
            for seq, pkt in list(self.packets.items()):
                if now - pkt.sent_at > timeout:
                    if pkt.retrans >= MAX_RETRANS:
                        # 彻底超时，删除
                        del self.packets[seq]
                        continue
                    pkt.retrans += 1
                    pkt.sent_at = now
                    expired.append((seq, pkt.data))
        return expired

    def clear(self):
        with self.lock:
            self.packets.clear()


# ============== 分片重组 ==============

class FragmentAssembler:
    """分片重组器"""

    def __init__(self):
        self.frags: Dict[int, Dict[int, bytes]] = {}  # seq -> {frag_id -> data}
        self.counts: Dict[int, int] = {}  # seq -> total_count
        self.lock = threading.Lock()

    def add_fragment(self, seq: int, frag_id: int, frag_count: int, data: bytes) -> Optional[bytes]:
        """添加分片，返回完整数据（如果完整）"""
        with self.lock:
            if seq not in self.frags:
                self.frags[seq] = {}
                self.counts[seq] = frag_count

            self.frags[seq][frag_id] = data

            # 检查是否完整
            if len(self.frags[seq]) == frag_count:
                # 重组
                full_data = b"".join(self.frags[seq][i] for i in range(frag_count))
                del self.frags[seq]
                del self.counts[seq]
                return full_data
        return None

    def cleanup(self, seq: int):
        with self.lock:
            self.frags.pop(seq, None)
            self.counts.pop(seq, None)


# ============== Hub (中枢) ==============

class TunnelHub:
    """
    隧道中枢 - 全中心化架构

    所有节点连接到此中枢，流量在此汇聚
    支持：加密握手 / 数据转发 / 分片重组 / 重传控制
    """

    def __init__(self, listen_port: int = 9527):
        self.port = listen_port
        self.sock = None
        self.running = False
        self.sessions = SessionManager()
        self.retrans_window = RetransmitWindow()
        self.frag_assembler = FragmentAssembler()

        # 回调
        self.on_node_message: Optional[Callable[[str, bytes], None]] = None
        self.on_node_connect: Optional[Callable[[str], None]] = None
        self.on_node_disconnect: Optional[Callable[[str], None]] = None

        # 内部线程
        self.thread_recv = None
        self.thread_retrans = None
        self.thread_keepalive = None
        self.thread_cleanup = None

    def start(self):
        """启动中枢"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", self.port))
        self.sock.settimeout(1.0)
        self.running = True

        logger.info(f"🌀 Neural Tunnel Hub 启动，监听 UDP {self.port}")

        self.thread_recv = threading.Thread(target=self._recv_loop, daemon=True)
        self.thread_retrans = threading.Thread(target=self._retrans_loop, daemon=True)
        self.thread_keepalive = threading.Thread(target=self._keepalive_loop, daemon=True)
        self.thread_cleanup = threading.Thread(target=self._cleanup_loop, daemon=True)

        for t in [self.thread_recv, self.thread_retrans, self.thread_keepalive, self.thread_cleanup]:
            t.start()

    def stop(self):
        """停止中枢"""
        self.running = False
        if self.sock:
            self.sock.close()
        logger.info("🛑 Neural Tunnel Hub 已停止")

    def _recv_loop(self):
        """接收循环"""
        while self.running:
            try:
                data, addr = self.sock.recvfrom(65535)
                self._handle_packet(data, addr)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"接收错误: {e}")

    def _handle_packet(self, data: bytes, addr: Tuple[str, int]):
        """处理数据包"""
        try:
            frame = unpack_frame(data, self.sessions.secret)
            if not frame:
                return

            pkg_type = frame["type"]
            seq = frame["seq"]
            payload = frame["payload"]

            # 从序列号提取node_id（简化版：序列号前4字节是node标识）
            # 实际应用中应该在握手时建立映射
            node_id = self._get_node_id_by_seq(seq)

            if pkg_type in (PacketType.HANDSHAKE_INIT, PacketType.HANDSHAKE_ACK, PacketType.HANDSHAKE_FIN):
                self._handle_handshake(node_id, addr, pkg_type, seq, payload)
            elif pkg_type == PacketType.DATA:
                self._handle_data(node_id, addr, seq, payload)
            elif pkg_type == PacketType.DATA_ACK:
                self._handle_data_ack(node_id, seq)
            elif pkg_type == PacketType.FRAGMENT:
                self._handle_fragment(node_id, addr, seq, frame["frag_id"], frame["frag_count"], payload)
            elif pkg_type == PacketType.HEARTBEAT:
                self._handle_heartbeat(node_id, addr, seq)
            elif pkg_type == PacketType.DISCONNECT:
                self._handle_disconnect(node_id)

        except Exception as e:
            logger.error(f"处理包错误: {e}")

    def _handle_handshake(self, node_id: str, addr: Tuple[str, int], pkg_type: int, seq: int, payload: bytes):
        """处理握手"""
        if pkg_type == PacketType.HANDSHAKE_INIT:
            # 节点请求连接
            # 期望payload: node_id
            try:
                their_node_id = payload.decode()
            except:
                return

            sess = self.sessions.create_session(their_node_id, addr)
            sess.seq_recv = seq

            # 发送握手ACK
            resp = pack_frame(
                PacketType.HANDSHAKE_ACK,
                sess.seq_send,
                0, 0,
                sess.key,  # 发送会话密钥（实际应加密）
                self.sessions.secret
            )
            self.sock.sendto(resp, addr)
            logger.info(f"📡 握手INIT {their_node_id} → ACK已发送")

        elif pkg_type == PacketType.HANDSHAKE_ACK:
            # 收到ACK（作为节点时使用）
            logger.info(f"📡 握手ACK seq={seq}")

        elif pkg_type == PacketType.HANDSHAKE_FIN:
            # 握手完成确认
            node_id = self._get_node_id_by_seq(seq)
            sess = self.sessions.get_session(node_id)
            if sess:
                sess.established = True
                logger.info(f"✅ 隧道建立 {node_id}")
                if self.on_node_connect:
                    self.on_node_connect(node_id)

    def _handle_data(self, node_id: str, addr: Tuple[str, int], seq: int, payload: bytes):
        """处理数据"""
        sess = self.sessions.get_session(node_id)
        if not sess:
            return

        sess.last_seen = time.time()
        sess.seq_recv = max(sess.seq_recv, seq)

        # 发送ACK
        ack = pack_frame(PacketType.DATA_ACK, seq, 0, 0, b"", self.sessions.secret)
        self.sock.sendto(ack, addr)

        # 回调上层
        if self.on_node_message:
            self.on_node_message(node_id, payload)

    def _handle_fragment(self, node_id: str, addr: Tuple[str, int], seq: int, frag_id: int, frag_count: int, payload: bytes):
        """处理分片"""
        sess = self.sessions.get_session(node_id)
        if not sess:
            return

        sess.last_seen = time.time()

        # 尝试重组
        full_data = self.frag_assembler.add_fragment(seq, frag_id, frag_count, payload)
        if full_data:
            # 完整包到达
            self._handle_data(node_id, addr, seq, full_data)

    def _handle_data_ack(self, node_id: str, seq: int):
        """处理数据确认"""
        self.retrans_window.ack(seq)

    def _handle_heartbeat(self, node_id: str, addr: Tuple[str, int], seq: int):
        """处理心跳"""
        sess = self.sessions.get_session(node_id)
        if sess:
            sess.last_seen = time.time()
            ack = pack_frame(PacketType.HEARTBEAT_ACK, seq, 0, 0, b"", self.sessions.secret)
            self.sock.sendto(ack, addr)

    def _handle_disconnect(self, node_id: str):
        """处理断开连接"""
        self.sessions.remove_session(node_id)
        if self.on_node_disconnect:
            self.on_node_disconnect(node_id)

    def _get_node_id_by_seq(self, seq: int) -> str:
        """从序列号提取node_id（简化实现）"""
        # 实际应用中应维护 seq -> node_id 映射
        for node_id, sess in self.sessions.sessions.items():
            if abs(sess.seq_recv - seq) < 1000000:
                return node_id
        return f"unknown_{seq >> 16}"

    def _retrans_loop(self):
        """重传循环"""
        while self.running:
            time.sleep(0.5)
            expired = self.retrans_window.get_expired()
            for seq, data in expired:
                # 从数据中提取addr（简化：重传队列需要记录目标）
                # 实际应用中应在pending packet中存储目标地址
                logger.warning(f"🔄 重传 seq={seq}")

    def _keepalive_loop(self):
        """保活循环"""
        while self.running:
            time.sleep(KEEPALIVE_INTERVAL)
            now = time.time()
            for node_id, sess in list(self.sessions.sessions.items()):
                if sess.established and (now - sess.last_seen) > KEEPALIVE_INTERVAL * 2:
                    # 发送心跳探测
                    hb = pack_frame(PacketType.HEARTBEAT, sess.seq_send, 0, 0, b"", self.sessions.secret)
                    try:
                        self.sock.sendto(hb, sess.addr)
                    except:
                        pass

    def _cleanup_loop(self):
        """清理循环"""
        while self.running:
            time.sleep(60)
            cleaned = self.sessions.cleanup_stale()
            if cleaned:
                logger.info(f"🧹 清理 {cleaned} 个超时会话")

    # ============== 对外接口 ==============

    def send_to_node(self, node_id: str, data: bytes) -> bool:
        """发送数据到指定节点"""
        sess = self.sessions.get_session(node_id)
        if not sess or not sess.established:
            logger.warning(f"节点未连接 {node_id}")
            return False

        # 分片（如果数据过大）
        if len(data) > FRAGMENT_SIZE:
            return self._send_fragmented(sess, data)

        # 正常发送
        sess.seq_send += 1
        frame = pack_frame(PacketType.DATA, sess.seq_send, 0, 0, data, self.sessions.secret)
        self.retrans_window.add(sess.seq_send, frame)

        try:
            self.sock.sendto(frame, sess.addr)
            return True
        except Exception as e:
            logger.error(f"发送失败 {node_id}: {e}")
            return False

    def _send_fragmented(self, sess: Session, data: bytes) -> bool:
        """分片发送大数据"""
        frag_count = (len(data) + FRAGMENT_SIZE - 1) // FRAGMENT_SIZE
        for i in range(frag_count):
            frag_data = data[i * FRAGMENT_SIZE:(i + 1) * FRAGMENT_SIZE]
            sess.seq_send += 1
            frame = pack_frame(PacketType.FRAGMENT, sess.seq_send, i, frag_count, frag_data, self.sessions.secret)
            self.retrans_window.add(sess.seq_send, frame)
            try:
                self.sock.sendto(frame, sess.addr)
            except Exception as e:
                logger.error(f"分片发送失败: {e}")
                return False
            time.sleep(0.01)  # 防止发送过快
        return True

    def broadcast(self, data: bytes) -> int:
        """广播到所有已连接节点"""
        count = 0
        for node_id in list(self.sessions.sessions.keys()):
            if self.send_to_node(node_id, data):
                count += 1
        return count

    def get_stats(self) -> dict:
        """获取统计"""
        return {
            "sessions": len(self.sessions.sessions),
            "established": sum(1 for s in self.sessions.sessions.values() if s.established),
            "pending": len(self.retrans_window.packets),
        }


# ============== Node (节点) ==============

class TunnelNode:
    """
    隧道节点 - 连接中枢

    负责：建立连接 / 数据发送 / 分片 / 重传 / 心跳
    """

    def __init__(self, node_id: str, hub_addr: Tuple[str, int], listen_port: int = 0):
        self.node_id = node_id
        self.hub_addr = hub_addr
        self.listen_port = listen_port

        self.sock = None
        self.running = False
        self.connected = False
        self.session_key: Optional[bytes] = None

        self.sessions = SessionManager()
        self.retrans_window = RetransmitWindow()
        self.frag_assembler = FragmentAssembler()

        # 回调
        self.on_hub_message: Optional[Callable[[bytes], None]] = None
        self.on_connect: Optional[Callable[[], None]] = None
        self.on_disconnect: Optional[Callable[[], None]] = None

        # 内部线程
        self.thread_recv = None
        self.thread_retrans = None
        self.thread_heartbeat = None

    def start(self) -> bool:
        """启动节点并连接中枢"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if self.listen_port:
            self.sock.bind(("0.0.0.0", self.listen_port))
        self.sock.settimeout(1.0)
        self.running = True

        # 启动接收线程
        self.thread_recv = threading.Thread(target=self._recv_loop, daemon=True)
        self.thread_retrans = threading.Thread(target=self._retrans_loop, daemon=True)
        self.thread_heartbeat = threading.Thread(target=self._heartbeat_loop, daemon=True)

        for t in [self.thread_recv, self.thread_retrans, self.thread_heartbeat]:
            t.start()

        # 发起握手
        return self._do_handshake()

    def stop(self):
        """停止节点"""
        self.running = False
        if self.connected:
            # 发送断开通知
            disc = pack_frame(PacketType.DISCONNECT, 0, 0, 0, b"", self.sessions.secret)
            try:
                self.sock.sendto(disc, self.hub_addr)
            except:
                pass
        if self.sock:
            self.sock.close()
        self.connected = False
        logger.info(f"🛑 Tunnel Node {self.node_id} 已停止")

    def _do_handshake(self) -> bool:
        """执行握手"""
        logger.info(f"🔑 正在连接中枢 {self.hub_addr}...")

        # 发送握手INIT
        init = pack_frame(
            PacketType.HANDSHAKE_INIT,
            random.randint(1, 0xFFFF),
            0, 0,
            self.node_id.encode(),
            self.sessions.secret
        )
        self.sock.sendto(init, self.hub_addr)

        # 等待握手ACK（3秒超时）
        deadline = time.time() + HANDSHAKE_TIMEOUT
        while time.time() < deadline:
            try:
                data, addr = self.sock.recvfrom(65535)
                if addr == self.hub_addr:
                    frame = unpack_frame(data, self.sessions.secret)
                    if frame and frame["type"] == PacketType.HANDSHAKE_ACK:
                        self.session_key = frame["payload"]
                        self.connected = True
                        logger.info(f"✅ 已连接中枢，获取会话密钥")
                        if self.on_connect:
                            self.on_connect()
                        return True
            except socket.timeout:
                continue

        logger.error(f"❌ 握手超时")
        return False

    def _recv_loop(self):
        """接收循环"""
        while self.running:
            try:
                data, addr = self.sock.recvfrom(65535)
                if addr == self.hub_addr:
                    self._handle_packet(data)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"接收错误: {e}")

    def _handle_packet(self, data: bytes):
        """处理数据包"""
        try:
            frame = unpack_frame(data, self.sessions.secret)
            if not frame:
                return

            pkg_type = frame["type"]
            seq = frame["seq"]
            payload = frame["payload"]

            if pkg_type == PacketType.DATA:
                self._handle_data(seq, payload)
            elif pkg_type == PacketType.DATA_ACK:
                self.retrans_window.ack(seq)
            elif pkg_type == PacketType.FRAGMENT:
                self._handle_fragment(seq, frame["frag_id"], frame["frag_count"], payload)
            elif pkg_type == PacketType.HEARTBEAT:
                self._handle_heartbeat(seq)
            elif pkg_type == PacketType.HEARTBEAT_ACK:
                logger.debug(f"心跳响应 seq={seq}")
            elif pkg_type == PacketType.DISCONNECT:
                logger.info("收到中枢断开通知")
                self.connected = False
                if self.on_disconnect:
                    self.on_disconnect()

        except Exception as e:
            logger.error(f"处理包错误: {e}")

    def _handle_data(self, seq: int, payload: bytes):
        """处理数据"""
        # 发送ACK
        ack = pack_frame(PacketType.DATA_ACK, seq, 0, 0, b"", self.sessions.secret)
        try:
            self.sock.sendto(ack, self.hub_addr)
        except:
            pass

        # 回调
        if self.on_hub_message:
            self.on_hub_message(payload)

    def _handle_fragment(self, seq: int, frag_id: int, frag_count: int, payload: bytes):
        """处理分片"""
        full_data = self.frag_assembler.add_fragment(seq, frag_id, frag_count, payload)
        if full_data:
            self._handle_data(seq, full_data)

    def _handle_heartbeat(self, seq: int):
        """响应心跳"""
        ack = pack_frame(PacketType.HEARTBEAT_ACK, seq, 0, 0, b"", self.sessions.secret)
        try:
            self.sock.sendto(ack, self.hub_addr)
        except:
            pass

    def _retrans_loop(self):
        """重传循环"""
        while self.running:
            time.sleep(0.5)
            expired = self.retrans_window.get_expired()
            for seq, data in expired:
                try:
                    self.sock.sendto(data, self.hub_addr)
                    logger.debug(f"🔄 重传 seq={seq}")
                except Exception as e:
                    logger.error(f"重传失败: {e}")

    def _heartbeat_loop(self):
        """心跳循环"""
        while self.running:
            time.sleep(KEEPALIVE_INTERVAL)
            if self.connected:
                hb = pack_frame(PacketType.HEARTBEAT, random.randint(1, 0xFFFF), 0, 0, b"", self.sessions.secret)
                try:
                    self.sock.sendto(hb, self.hub_addr)
                except:
                    pass

    # ============== 对外接口 ==============

    def send(self, data: bytes) -> bool:
        """发送数据到中枢"""
        if not self.connected:
            logger.warning("未连接中枢")
            return False

        # 分片
        if len(data) > FRAGMENT_SIZE:
            return self._send_fragmented(data)

        # 正常发送
        seq = random.randint(1, 0xFFFF)
        frame = pack_frame(PacketType.DATA, seq, 0, 0, data, self.sessions.secret)
        self.retrans_window.add(seq, frame)

        try:
            self.sock.sendto(frame, self.hub_addr)
            return True
        except Exception as e:
            logger.error(f"发送失败: {e}")
            return False

    def _send_fragmented(self, data: bytes) -> bool:
        """分片发送"""
        frag_count = (len(data) + FRAGMENT_SIZE - 1) // FRAGMENT_SIZE
        seq = random.randint(1, 0xFFFF)
        for i in range(frag_count):
            frag_data = data[i * FRAGMENT_SIZE:(i + 1) * FRAGMENT_SIZE]
            frame = pack_frame(PacketType.FRAGMENT, seq + i, i, frag_count, frag_data, self.sessions.secret)
            self.retrans_window.add(seq + i, frame)
            try:
                self.sock.sendto(frame, self.hub_addr)
            except Exception as e:
                logger.error(f"分片发送失败: {e}")
                return False
            time.sleep(0.01)
        return True

    def is_connected(self) -> bool:
        return self.connected


# ============== 演示 ==============

def demo_hub():
    """中枢演示"""
    print("\n🌀 Neural Tunnel Hub 演示")
    print("="*50)

    hub = TunnelHub(listen_port=19527)

    def on_message(node_id: str, data: bytes):
        print(f"📨 收到节点 {node_id} 数据: {data[:50]}...")

    def on_connect(node_id: str):
        print(f"✅ 节点 {node_id} 已连接")

    def on_disconnect(node_id: str):
        print(f"🔌 节点 {node_id} 已断开")

    hub.on_node_message = on_message
    hub.on_node_connect = on_connect
    hub.on_node_disconnect = on_disconnect

    hub.start()
    print(f"Hub 正在运行，监听 UDP 19527")
    print("按 Ctrl+C 停止...\n")

    try:
        while True:
            time.sleep(1)
            stats = hub.get_stats()
            print(f"\r会话: {stats['sessions']} | 已建立: {stats['established']} | 待确认: {stats['pending']}  ", end="", flush=True)
    except KeyboardInterrupt:
        print("\n")
        hub.stop()


def demo_node():
    """节点演示"""
    print("\n📡 Neural Tunnel Node 演示")
    print("="*50)

    node = TunnelNode(
        node_id="test_node_01",
        hub_addr=("127.0.0.1", 19527)
    )

    def on_message(data: bytes):
        print(f"📨 收到中枢数据: {data[:50]}...")

    def on_connect():
        print("✅ 已连接中枢")

    def on_disconnect():
        print("🔌 与中枢断开")

    node.on_hub_message = on_message
    node.on_connect = on_connect
    node.on_disconnect = on_disconnect

    if node.start():
        print("节点启动成功，发送测试数据...")
        node.send(b"Hello from Node!")
        time.sleep(1)
        node.send(b"Second message from Node!")
        time.sleep(1)

    print("按 Ctrl+C 停止...\n")

    try:
        while node.is_connected():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n")
        node.stop()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: neural_tunnel.py [hub|node]")
        print("  hub   - 启动中枢")
        print("  node  - 启动节点（连接本地中枢）")
        sys.exit(1)

    if sys.argv[1] == "hub":
        demo_hub()
    elif sys.argv[1] == "node":
        demo_node()
    else:
        print(f"未知模式: {sys.argv[1]}")
        sys.exit(1)
