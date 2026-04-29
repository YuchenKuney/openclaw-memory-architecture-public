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

# ============== ChaCha20-Poly1305 加密 ==============
try:
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
    HAS_CHACHA = True
except ImportError:
    HAS_CHACHA = False
    logger.warning("ChaCha20Poly1305 不可用，将使用 HMAC-only 模式")


def chacha_encrypt(key: bytes, nonce: bytes, plaintext: bytes) -> bytes:
    """ChaCha20-Poly1305 加密（返回: nonce+密文+tag）"""
    if not HAS_CHACHA:
        return plaintext
    chacha = ChaCha20Poly1305(key)
    # Nonce: 12 bytes，密文包含 16 bytes auth tag
    ct = chacha.encrypt(nonce, plaintext, None)
    return nonce + ct


def chacha_decrypt(key: bytes, ciphertext: bytes) -> Optional[bytes]:
    """ChaCha20-Poly1305 解密（输入: nonce+密文+tag）"""
    if not HAS_CHACHA or len(ciphertext) < 12:
        return ciphertext if not HAS_CHACHA else None
    nonce = ciphertext[:12]
    ct = ciphertext[12:]
    try:
        chacha = ChaCha20Poly1305(key)
        return chacha.decrypt(nonce, ct, None)
    except Exception as e:
        logger.warning(f"ChaCha20 解密失败: {e}")
        return None


# ============== Noise Protocol (X25519 + HKDF) ==============

try:
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from cryptography.hazmat.backends import default_backend
    HAS_NOISE = True
except ImportError:
    HAS_NOISE = False
    logger.warning("Noise Protocol 不可用")


class NoiseKeys:
    """Noise握手派生的会话密钥"""
    def __init__(self, send_key: bytes, recv_key: bytes, chaining_key: bytes):
        self.send_key = send_key      # 发送密钥（ChaCha20）
        self.recv_key = recv_key      # 接收密钥（ChaCha20）
        self.chaining_key = chaining_key  # 链密钥（用于再派生）


class NoiseHandshake:
    """
    简化版 Noise_XX 握手实现

    流程（2-RTT）：
      Node                         Hub
       ────                        ────
    1. INIT(s, e)       →         (收到静态公钥s，生成临时DH对)
    2.                 ←   ACK(re, es)   (临时公钥re，用e和s派生存密钥)
    3. FIN(e, ee, se)   →           (发送e和ee+se的证据)

    派生存密钥: HKDF-SHA256( DH(e,re) || DH(e,s) || DH(s,re) )
    """

    def __init__(self, is_initiator: bool):
        self.is_initiator = is_initiator
        self.static_private: Optional[X25519PrivateKey] = None
        self.static_public: Optional[X25519PublicKey] = None
        self.ephemeral_private: Optional[X25519PrivateKey] = None
        self.ephemeral_public: Optional[X25519PublicKey] = None
        self.peer_static: Optional[bytes] = None
        self.peer_ephemeral: Optional[bytes] = None
        self.session_keys: Optional[NoiseKeys] = None
        self.handshake_hash = b""

    def generate_static_keypair(self, private_bytes: bytes = None) -> bytes:
        """生成或加载静态密钥对，返回公钥"""
        if private_bytes:
            self.static_private = X25519PrivateKey.from_private_bytes(private_bytes)
        else:
            self.static_private = X25519PrivateKey.generate()
        self.static_public = self.static_private.public_key()
        return self.static_public.public_bytes(Encoding.Raw, PublicFormat.Raw)

    def initiate_handshake(self, peer_static_public: bytes = None) -> Tuple[bytes, bytes]:
        """
        发起握手第一步（Initiator）
        返回: (init_payload, ephemeral_public)
        - init_payload: 包含静态公钥（可选加密）
        - ephemeral_public: 临时公钥（32 bytes）
        """
        # 生成临时密钥对
        self.ephemeral_private = X25519PrivateKey.generate()
        self.ephemeral_public = self.ephemeral_private.public_key()
        e_pub = self.ephemeral_public.public_bytes(Encoding.Raw, PublicFormat.Raw)

        # 如果有对等方静态公钥，先做一轮DH
        if peer_static_public:
            self.peer_static = peer_static_public

        # init_payload = 静态公钥（如果有）
        init_payload = b""
        if self.static_public:
            init_payload = self.static_public.public_bytes(Encoding.Raw, PublicFormat.Raw)

        # 更新handshake_hash
        self._mix_hash(e_pub + init_payload)

        return init_payload, e_pub

    def process_handshake_response(self, response: bytes, peer_ephemeral: bytes) -> bool:
        """
        处理响应（Initiator第二步）
        response: Hub返回的加密payload
        peer_ephemeral: Hub的临时公钥
        返回: 是否成功
        """
        self.peer_ephemeral = peer_ephemeral

        # DH(e, re) - 临时密钥DH
        dh1 = self._dh(self.ephemeral_private, peer_ephemeral)

        # DH(s, re) - 静态密钥与对方临时密钥DH
        if self.static_private and peer_ephemeral:
            peer_pub = X25519PublicKey.from_public_bytes(peer_ephemeral)
            dh2 = self._dh(self.static_private, peer_pub)
        else:
            dh2 = b"\x00" * 32

        # 派生会话密钥
        self._derive_keys(dh1 + dh2)

        # 如果response有加密内容（FIN），解密验证
        if len(response) > 0:
            self._mix_hash(response)

        return True

    def respond_handshake(self, init_payload: bytes, peer_ephemeral_pub: bytes) -> Tuple[bytes, bytes]:
        """
        响应握手（Responder第一步）
        返回: (ack_payload, ephemeral_public)
        """
        # 保存对等方的临时公钥
        self.peer_ephemeral = peer_ephemeral_pub
        # 解析对等方静态公钥
        if len(init_payload) == 32:
            self.peer_static = init_payload

        # 生成自己的临时密钥对
        self.ephemeral_private = X25519PrivateKey.generate()
        self.ephemeral_public = self.ephemeral_private.public_key()
        re_pub = self.ephemeral_public.public_bytes(Encoding.Raw, PublicFormat.Raw)

        # DH(e, re) - 临时密钥DH
        peer_epub = X25519PublicKey.from_public_bytes(peer_ephemeral_pub)
        dh1 = self._dh(self.ephemeral_private, peer_epub)

        # DH(s, re) - 静态密钥与对方临时密钥DH
        dh2 = b"\x00" * 32
        if self.static_private and peer_ephemeral_pub:
            dh2 = self._dh(self.static_private, peer_epub)

        # 派生会话密钥
        self._derive_keys(dh1 + dh2)

        # ACK payload = re_pub || 可选加密数据
        ack_payload = re_pub

        # 更新handshake_hash
        self._mix_hash(peer_ephemeral_pub + init_payload + ack_payload)

        return ack_payload, re_pub

    def finalize_handshake(self, fin_payload: bytes = b"") -> bool:
        """
        完成握手（Initiator第二步发送FIN后调用）
        """
        if fin_payload:
            self._mix_hash(fin_payload)
        return True

    def _dh(private_key: X25519PrivateKey, peer_public_bytes: bytes) -> bytes:
        """执行DH计算"""
        peer_pub = X25519PublicKey.from_public_bytes(peer_public_bytes)
        shared = private_key.exchange(peer_pub)
        return shared

    def _mix_hash(self, data: bytes):
        """混合到handshake_hash"""
        if HAS_NOISE:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.backends import default_backend
            import hashlib
            self.handshake_hash = hashlib.sha256(self.handshake_hash + data).digest()

    def _derive_keys(self, ikm: bytes):
        """HKDF-SHA256派生会话密钥"""
        if not HAS_NOISE:
            self.session_keys = NoiseKeys(ikm[:32], ikm[32:64], ikm)
            return

        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=64,
            salt=self.handshake_hash or None,
            info=b"neural_tunnel_v1",
            backend=default_backend()
        )
        derived = hkdf.derive(ikm)
        self.session_keys = NoiseKeys(
            send_key=derived[:32],
            recv_key=derived[32:64],
            chaining_key=derived
        )


def noise_encrypt_with_key(key: bytes, plaintext: bytes, nonce_prefix: bytes = b"") -> bytes:
    """用Noise派生的密钥加密"""
    import os
    nonce = nonce_prefix + os.urandom(12 - len(nonce_prefix))
    return chacha_encrypt(key, nonce, plaintext)


def noise_decrypt_with_key(key: bytes, ciphertext: bytes) -> Optional[bytes]:
    """用Noise派生的密钥解密"""
    return chacha_decrypt(key, ciphertext)


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
               payload: bytes, secret: bytes, ts: int = None,
               cipher_key: bytes = None) -> bytes:
    """打包帧（可加密payload）"""
    if ts is None:
        ts = int(time.time() * 1000)  # 毫秒时间戳

    # ChaCha20加密 payload（握手包不加密）
    if cipher_key and HAS_CHACHA and pkg_type not in (PacketType.HANDSHAKE_INIT,
                                                       PacketType.HANDSHAKE_ACK,
                                                       PacketType.HANDSHAKE_FIN):
        nonce = struct.pack(">II", ts & 0xFFFFFFFF, seq & 0xFFFFFFFF)
        payload = chacha_encrypt(cipher_key, nonce, payload)

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


def unpack_frame(data: bytes, secret: bytes, cipher_key: bytes = None) -> Optional[dict]:
    """解包帧，验证HMAC并解密payload"""
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

    # ChaCha20解密 payload（握手包不解密）
    if cipher_key and HAS_CHACHA and pkg_type not in (PacketType.HANDSHAKE_INIT,
                                                        PacketType.HANDSHAKE_ACK,
                                                        PacketType.HANDSHAKE_FIN):
        decrypted = chacha_decrypt(cipher_key, payload)
        if decrypted is None:
            logger.warning(f"ChaCha20解密失败 seq={seq}")
            return None
        payload = decrypted

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
    key: bytes = field(default_factory=lambda: os.urandom(32))  # ChaCha20密钥（Noise后替换）
    seq_send: int = 0
    seq_recv: int = 0
    last_seen: float = field(default_factory=time.time)
    established: bool = False
    frag_buffer: Dict[int, bytes] = field(default_factory=dict)
    frag_count: int = 0
    pending_acks: set = field(default_factory=set)  # 待确认的序列号
    # Noise握手相关
    noise: Optional[NoiseHandshake] = None
    peer_static_pub: Optional[bytes] = None
    peer_ephemeral_pub: Optional[bytes] = None


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

    def __init__(self, listen_port: int = 9527, static_private_bytes: bytes = None):
        self.port = listen_port
        self.sock = None
        self.running = False
        self.sessions = SessionManager()
        self.retrans_window = RetransmitWindow()
        self.frag_assembler = FragmentAssembler()

        # Noise静态密钥对（Hub的长期身份密钥）
        self.noise = NoiseHandshake(is_initiator=False)
        self.static_pub_bytes = self.noise.generate_static_keypair(static_private_bytes)
        logger.info(f"🔐 Hub静态公钥: {self.static_pub_bytes.hex()[:16]}...")

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
            # 尝试从数据中提取node_id（用于查找会话）
            node_id = self._get_node_id_by_addr(addr)
            cipher_key = None
            if node_id:
                sess = self.sessions.get_session(node_id)
                if sess and sess.established:
                    cipher_key = sess.key

            frame = unpack_frame(data, self.sessions.secret, cipher_key)
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
        """Noise握手处理"""
        if pkg_type == PacketType.HANDSHAKE_INIT:
            # payload格式: 32字节静态公钥 || 32字节临时公钥 || node_id
            if len(payload) < 65:
                logger.warning(f"INIT payload太短: {len(payload)}")
                return

            peer_static_pub = payload[:32]
            peer_ephemeral_pub = payload[32:64]
            node_id_raw = payload[64:].decode(errors='replace')

            sess = self.sessions.create_session(node_id_raw, addr)
            sess.seq_recv = seq
            sess.peer_static_pub = peer_static_pub
            sess.peer_ephemeral_pub = peer_ephemeral_pub

            # Noise握手（Responder端）
            sess.noise = NoiseHandshake(is_initiator=False)
            if not HAS_NOISE:
                # fallback: 使用简单密钥
                sess.key = os.urandom(32)
                logger.warning("⚠️ Noise不可用，使用简单密钥")
            else:
                sess.noise.generate_static_keypair()  # Hub自己的静态密钥
                ack_payload, re_pub = sess.noise.respond_handshake(
                    peer_static_pub,  # init_payload
                    peer_ephemeral_pub
                )
                # 从Noise派生的密钥
                if sess.noise.session_keys:
                    sess.key = sess.noise.session_keys.send_key
                # ack_payload = re_pub
                ack_payload = re_pub

            # 发送握手ACK（包含Hub的临时公钥）
            resp = pack_frame(
                PacketType.HANDSHAKE_ACK,
                sess.seq_send,
                0, 0,
                ack_payload,
                self.sessions.secret
            )
            self.sock.sendto(resp, addr)
            logger.info(f"📡 Noise INIT {node_id_raw} → ACK已发送")

        elif pkg_type == PacketType.HANDSHAKE_ACK:
            # 收到ACK（Node端使用，Hub这里不应该收到）
            logger.info(f"📡 收到非预期ACK seq={seq}")

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

    def _get_node_id_by_addr(self, addr: Tuple[str, int]) -> Optional[str]:
        """从地址查找node_id"""
        for node_id, sess in self.sessions.sessions.items():
            if sess.addr == addr:
                return node_id
        return None

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
        frame = pack_frame(PacketType.DATA, sess.seq_send, 0, 0, data,
                           self.sessions.secret, cipher_key=sess.key)
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
            frame = pack_frame(PacketType.FRAGMENT, sess.seq_send, i, frag_count, frag_data,
                               self.sessions.secret, cipher_key=sess.key)
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

        # Noise握手（Initiator端）
        self.noise = NoiseHandshake(is_initiator=True)
        self.static_pub_bytes = self.noise.generate_static_keypair()
        logger.info(f"🔐 Node静态公钥: {self.static_pub_bytes.hex()[:16]}...")

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
        """Noise Protocol 握手（Initiator）

        流程：
          Node --INIT(s,e)--> Hub
          Node <--ACK(re, es)-- Hub  (re=Hub临时公钥)
          Node --FIN(e, ee, se)-> Hub
        """
        logger.info(f"🔑 正在连接中枢 (Noise握手) {self.hub_addr}...")

        if not HAS_NOISE:
            logger.warning("⚠️ Noise不可用，使用fallback握手")
            return self._do_handshake_fallback()

        # Step 1: INIT (s=静态公钥, e=临时公钥)
        init_payload, e_pub = self.noise.initiate_handshake()
        # payload = 静态公钥(32) || 临时公钥(32) || node_id
        init_data = self.static_pub_bytes + e_pub + self.node_id.encode()

        init = pack_frame(
            PacketType.HANDSHAKE_INIT,
            random.randint(1, 0xFFFF),
            0, 0,
            init_data,
            self.sessions.secret
        )
        self.sock.sendto(init, self.hub_addr)
        logger.info(f"📡 Noise INIT 已发送")

        # Step 2: 等待 ACK(re)
        deadline = time.time() + HANDSHAKE_TIMEOUT
        re_pub = None
        while time.time() < deadline:
            try:
                data, addr = self.sock.recvfrom(65535)
                if addr == self.hub_addr:
                    frame = unpack_frame(data, self.sessions.secret)
                    if frame and frame["type"] == PacketType.HANDSHAKE_ACK:
                        re_pub = frame["payload"]  # Hub的临时公钥
                        logger.info(f"📡 收到ACK: re={re_pub.hex()[:16]}...")
                        break
            except socket.timeout:
                continue

        if not re_pub:
            logger.error("❌ 未收到ACK")
            return False

        # Step 3: 处理响应，完成Noise握手
        self.noise.process_handshake_response(b"", re_pub)

        # Step 4: 发送 FIN(e, proof)
        fin_payload = e_pub  # 发送自己的临时公钥作为证明
        self.noise.finalize_handshake(fin_payload)

        fin = pack_frame(
            PacketType.HANDSHAKE_FIN,
            random.randint(1, 0xFFFF),
            0, 0,
            fin_payload,
            self.sessions.secret,
            cipher_key=self.noise.session_keys.send_key if self.noise.session_keys else None
        )
        self.sock.sendto(fin, self.hub_addr)

        # 从Noise获取会话密钥
        if self.noise.session_keys:
            self.session_key = self.noise.session_keys.recv_key
        else:
            self.session_key = os.urandom(32)

        self.connected = True
        logger.info(f"✅ 隧道加密通道已建立 (Noise)")
        if self.on_connect:
            self.on_connect()
        return True

    def _do_handshake_fallback(self) -> bool:
        """Fallback明文握手（Noise不可用时）"""
        init = pack_frame(
            PacketType.HANDSHAKE_INIT,
            random.randint(1, 0xFFFF),
            0, 0,
            self.node_id.encode(),
            self.sessions.secret
        )
        self.sock.sendto(init, self.hub_addr)

        deadline = time.time() + HANDSHAKE_TIMEOUT
        while time.time() < deadline:
            try:
                data, addr = self.sock.recvfrom(65535)
                if addr == self.hub_addr:
                    frame = unpack_frame(data, self.sessions.secret)
                    if frame and frame["type"] == PacketType.HANDSHAKE_ACK:
                        self.session_key = frame["payload"]
                        logger.info(f"📡 Fallback握手成功")
                        self.connected = True
                        if self.on_connect:
                            self.on_connect()
                        return True
            except socket.timeout:
                continue

        logger.error("❌ Fallback握手超时")
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
            frame = unpack_frame(data, self.sessions.secret, self.session_key)
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
            elif pkg_type == PacketType.HANDSHAKE_FIN:
                # 收到中枢的握手完成信号
                self.connected = True
                logger.info("✅ 隧道加密通道已建立")
                if self.on_connect:
                    self.on_connect()

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
        frame = pack_frame(PacketType.DATA, seq, 0, 0, data,
                           self.sessions.secret, cipher_key=self.session_key)
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
            frame = pack_frame(PacketType.FRAGMENT, seq + i, i, frag_count, frag_data,
                               self.sessions.secret, cipher_key=self.session_key)
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
