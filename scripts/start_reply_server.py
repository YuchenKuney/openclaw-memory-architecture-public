#!/usr/bin/env python3
"""ReplyServer - 飞书卡片按钮回调处理（完整版）"""
import sys, os, time, json as _json, base64, threading, http.server, socketserver
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from urllib.parse import urlparse, parse_qs

WORKSPACE = '/root/.openclaw/workspace'
sys.path.insert(0, WORKSPACE)
sys.path.insert(0, f'{WORKSPACE}/clawkeeper')
os.chdir(f'{WORKSPACE}/clawkeeper')

# 加载环境变量
if os.path.exists('/etc/environment'):
    with open('/etc/environment') as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                v = v.strip('"')
                os.environ.setdefault(k, v)

# 读取加密密钥
ENCRYPT_KEY = os.environ.get("FEISHU_ENCRYPT_KEY", "${FEISHU_ENCRYPT_KEY}")
log = lambda msg: (sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n"), sys.stdout.flush())

from reply_handler import PendingRegistry
registry = PendingRegistry()

# ============ 加密/解密 ============
def decrypt_feishu_payload(encrypt_str: str, encrypt_key: str) -> dict:
    """
    Feishu 加密回调：AES-256-CBC + PKCS7 padding + Base64
    token = base64_decode(encrypt_str)
    iv = token[:16]
    ciphertext = token[16:]
    plaintext = AES_decrypt(ciphertext, key, iv)
    """
    try:
        key_bytes = encrypt_key.encode('utf-8')  # 应该是32字节
        if len(key_bytes) != 32:
            log(f"⚠️ Encrypt key 长度错误: {len(key_bytes)}，期望32")
            return {}

        token = base64.b64decode(encrypt_str)
        iv = token[:16]
        ciphertext = token[16:]

        cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()

        unpadder = padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded) + unpadder.finalize()
        return _json.loads(plaintext.decode('utf-8'))
    except Exception as e:
        log(f"⚠️ 解密失败: {e}")
        return {}

# ============ 处理按钮回调 ============
def handle_action(payload: dict) -> dict:
    """
    统一处理入口：识别格式 → 提取 action/approval_id → 更新 registry
    返回 (status_text, is_handled)
    """
    # 格式1: schema 2.0
    if payload.get("schema") == "2.0":
        header = payload.get("header", {})
        event = payload.get("event", {})
        if header.get("event_type") == "card.action.trigger":
            av = event.get("action", {}).get("value", {})
            action_t = av.get("action", "").upper()
            approval_id = av.get("approval_id", "")
            log(f"[schema2.0] action={action_t} id={approval_id}")
            return _do_resolve(action_t, approval_id)

    # 格式2: 未加密直接回调 (app_id 在根目录)
    if "app_id" in payload and "action" in payload:
        av = payload.get("action", {}).get("value", {})
        action_t = av.get("action", "").upper()
        approval_id = av.get("approval_id", "")
        log(f"[direct] action={action_t} id={approval_id}")
        return _do_resolve(action_t, approval_id)

    # 格式3: 加密回调
    if "encrypt" in payload:
        decrypted = decrypt_feishu_payload(payload["encrypt"], ENCRYPT_KEY)
        if decrypted:
            return handle_action(decrypted)
        return ("解密失败", False)

    # 格式4: url_verification
    if payload.get("type") == "url_verification":
        return ("url_verification", True)

    log(f"⚠️ 未知格式: {list(payload.keys())}")
    return ("未知格式", False)

def _do_resolve(action_t: str, approval_id: str) -> tuple:
    if not approval_id:
        return ("无approval_id", False)
    if action_t == "ALLOW":
        registry.resolve(approval_id, "approved")
        return ("允许", True)
    elif action_t == "DENY":
        registry.resolve(approval_id, "rejected")
        return ("拒绝", True)
    else:
        log(f"⚠️ 未知action: {action_t}")
        return (f"未知action:{action_t}", False)

# ============ HTTP Server ============
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass

    def do_POST(self):
        if self.path not in ("/feishu/reply", "/feishu/approval"):
            self.send_response(404); self.end_headers(); return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        log(f"POST {self.path} len={len(body)}")

        try:
            payload = _json.loads(body)
        except:
            payload = {}

        status_text, handled = handle_action(payload)

        if payload.get("type") == "url_verification":
            challenge = payload.get("challenge", "")
            resp = _json.dumps({"challenge": challenge}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(resp)
            log(f"✅ url_verification: {challenge}")
            return

        if handled:
            result = {
                "code": 0, "msg": "success",
                "data": {"template_variable": {"status": "✅ " + status_text}},
                "toast": {"type": "success", "content": "✅ " + status_text}
            }
        else:
            result = {"code": 0, "msg": status_text}

        resp = _json.dumps(result).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(resp)
        log(f"✅ 响应: {status_text} (handled={handled})")

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        challenge = params.get("challenge", [""])[0]
        if challenge:
            resp = _json.dumps({"challenge": challenge}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(resp)
            log(f"✅ GET challenge: {challenge}")
        else:
            self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers()
            self.wfile.write(b"OK")

class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

# 清理旧进程
try:
    with open(f'{WORKSPACE}/clawkeeper/reply_server.pid') as f:
        old_pid = int(f.read().strip())
    os.kill(old_pid, 0)
    os.kill(old_pid, 9)
    log(f"Killed old PID: {old_pid}")
except: pass

time.sleep(0.5)

server = ReusableTCPServer(("0.0.0.0", 8765), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()

my_pid = os.getpid()
with open(f'{WORKSPACE}/clawkeeper/reply_server.pid', 'w') as f:
    f.write(str(my_pid))

log(f"✅ ReplyServer PID={my_pid} on 0.0.0.0:8765")
log(f"回调地址: http://46.250.233.112:8765/feishu/reply")
log(f"Encrypt Key: {'✅ loaded' if ENCRYPT_KEY and '${' not in ENCRYPT_KEY else '⚠️ NOT SET'}")

while True:
    time.sleep(3600)
