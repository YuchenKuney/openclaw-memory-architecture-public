#!/usr/bin/env python3
"""
飞书回复处理器 — 监听群组消息，执行「允许/拒绝」审批
与 v8 interceptor.py 联动：当坤哥回复「允许」或「拒绝」时，
自动更新 pending_actions，解除拦截或保持阻断。

工作原理：
  群组机器人收到消息 → 解析命令 → 更新 pending_registry → 触发 callback → interceptor 恢复/阻断 AI
"""

import os
import sys
import json
import time
import threading
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ============ 环境变量加载 ============
if os.path.exists('/etc/environment'):
    with open('/etc/environment') as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                v = v.strip('"')
                os.environ.setdefault(k, v)

# ============ Pending Registry（与 interceptor 共享） ============
PENDING_FILE = "/root/.openclaw/workspace/.pending_actions.json"


class PendingRegistry:
    """轻量级待审批注册表（文件共享，interceptor 和 reply_handler 共用）"""

    def __init__(self, path=PENDING_FILE):
        self.path = path
        self._lock = threading.Lock()
        self._callbacks = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    self._data = json.load(f)
            except:
                self._data = {}
        else:
            self._data = {}

    def _save(self):
        with open(self.path, 'w') as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def add(self, action_id: str, info: dict, callback=None):
        with self._lock:
            self._data[action_id] = {
                **info,
                "status": "pending",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "resolved_at": None
            }
            self._callbacks[action_id] = callback
            self._save()
        print(f"[PendingRegistry] 新增待审批: {action_id} | {info.get('message', info.get('path', 'N/A'))}")

    def resolve(self, action_id: str, status: str) -> dict:
        with self._lock:
            if action_id not in self._data:
                # 模糊匹配（取最新的）
                candidates = [k for k in self._data if self._data[k].get("status") == "pending"]
                if candidates:
                    action_id = candidates[-1]
                    print(f"[PendingRegistry] 模糊匹配到: {action_id}")

            if action_id in self._data:
                self._data[action_id]["status"] = status
                self._data[action_id]["resolved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                info = dict(self._data[action_id])
                self._save()

                # 触发回调
                if action_id in self._callbacks and self._callbacks[action_id]:
                    try:
                        self._callbacks[action_id](status, action_id, info)
                    except Exception as e:
                        print(f"[PendingRegistry] 回调异常: {e}")

                return info
            return {}

    def get_status(self, action_id: str) -> str:
        return self._data.get(action_id, {}).get("status", "unknown")

    def is_approved(self, action_id: str) -> bool:
        return self.get_status(action_id) == "approved"

    def list_pending(self):
        return {k: v for k, v in self._data.items() if v.get("status") == "pending"}

    def register_callback(self, action_id: str, callback):
        self._callbacks[action_id] = callback


# ============ 飞书回复解析 ============
def parse_approval_command(text: str) -> tuple:
    """
    解析坤哥的回复命令
    返回: (action_type, action_id or None)
    
    支持格式：
      - "允许" / "允许 test-001" → ("approve", "test-001")
      - "拒绝" / "拒绝 test-001" → ("reject", "test-001")
      - "允许 test-001 操作" → ("approve", "test-001")
      - "拒绝所有" → ("reject", "all")
    """
    text = text.strip()
    lower = text.lower()

    # 批准
    if lower in ("允许", "通过", "yes", "y", "approve", "allow", "ok"):
        return ("approve", None)
    # 拒绝
    if lower in ("拒绝", "否决", "no", "n", "reject", "deny"):
        return ("reject", None)
    # 批准 + ID
    if lower.startswith("允许 ") or lower.startswith("通过 "):
        parts = text.split()
        cmd = parts[0]
        action_id = parts[1] if len(parts) > 1 else None
        return ("approve", action_id)
    # 拒绝 + ID
    if lower.startswith("拒绝 ") or lower.startswith("否决 "):
        parts = text.split()
        cmd = parts[0]
        action_id = parts[1] if len(parts) > 1 else None
        return ("reject", action_id)
    # 拒绝所有
    if "拒绝所有" in text:
        return ("reject", "all")
    # 允许所有
    if "允许所有" in text:
        return ("approve", "all")

    return (None, None)


def handle_reply(action_type: str, action_id: str, registry: PendingRegistry):
    """
    处理审批回复，更新 pending 状态并通知相关模块
    """
    if action_id == "all":
        # 处理所有待审批
        pending = registry.list_pending()
        if not pending:
            print("[ReplyHandler] 没有待审批的操作")
            return
        for aid, info in pending.items():
            _resolve_and_notify(registry, aid, action_type)
    elif action_id:
        _resolve_and_notify(registry, action_id, action_type)
    else:
        # 处理最新的一个
        pending = registry.list_pending()
        if not pending:
            print("[ReplyHandler] 没有待审批的操作")
            return
        latest_id = list(pending.keys())[-1]
        _resolve_and_notify(registry, latest_id, action_type)


def _resolve_and_notify(registry, action_id, action_type):
    status = "approved" if action_type == "approve" else "rejected"
    info = registry.resolve(action_id, status)
    if info:
        path = info.get("path", info.get("message", "unknown"))
        emoji = "✅" if status == "approved" else "❌"
        print(f"[ReplyHandler] {emoji} {action_id} → {status} | 操作: {path}")
    else:
        print(f"[ReplyHandler] ⚠️ 未找到 {action_id}")


# ============ 飞书消息监听（HTTP Server） ============
class ReplyServer:
    """
    接收飞书群组消息的 HTTP Server
    飞书机器人收到「允许」「拒绝」等命令 → 解析 → 更新 pending → 通知 interceptor
    """

    def __init__(self, port=8765, registry=None):
        self.port = port
        self.registry = registry or PendingRegistry()
        self._server = None

    def handle_feishu_event(self, payload: dict):
        """处理飞书事件回调"""
        try:
            # 提取消息内容
            event = payload.get("event", {})
            msg_type = event.get("msg_type", "")
            content_str = event.get("content", "{}")

            if msg_type == "text":
                content = json.loads(content_str)
                text = content.get("text", "").strip()
            elif msg_type == "card" or "action_value" in payload:
                # 卡片按钮回调
                action_value_str = payload.get("action_value", "")
                try:
                    action_value = json.loads(action_value_str)
                    action_type = action_value.get("action")
                    action_id = action_value.get("id")
                    if action_type and action_id:
                        handle_reply(action_type, action_id, self.registry)
                        status_text = '允许' if action_type == 'approve' else '拒绝'
                        return {"code": 0, "msg": f"✅ 卡片审批完成: {status_text}"}
                except:
                    pass
                return {"code": 0, "msg": "卡片回调已处理"}
            else:
                return {"code": 0, "msg": "不支持的消息类型"}

            # 解析命令
            action_type, action_id = parse_approval_command(text)
            if not action_type:
                return {"code": 0, "msg": f"未识别命令: {text}"}

            # 处理审批
            handle_reply(action_type, action_id, self.registry)

            # 回复确认
            confirm_text = f"✅ 已{action_type == 'approve' and '允许' or '拒绝'}审批" if not action_id else f"✅ 已{action_type == 'approve' and '允许' or '拒绝'}: {action_id}"
            return {"code": 0, "msg": confirm_text}

        except Exception as e:
            return {"code": -1, "msg": str(e)}

    def start(self):
        """启动 HTTP Server（后台线程）"""
        import http.server
        import socketserver

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path == "/feishu/reply" or self.path == "/feishu/approval":
                    content_length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(content_length).decode("utf-8")
                    try:
                        payload = json.loads(body)
                        # 飞书事件订阅验证（url_verification）
                        if payload.get("type") == "url_verification":
                            import os
                            challenge = payload.get("challenge", "")
                            expected_token = os.environ.get("FEISHU_VERIFICATION_TOKEN", "")
                            received_token = payload.get("token", "")
                            print(f"[ReplyServer] url_verification: challenge={challenge}")
                            if expected_token and received_token != expected_token:
                                print(f"[ReplyServer] ❌ Token mismatch")
                                self.send_response(403)
                                self.end_headers()
                                return
                            self.send_response(200)
                            self.send_header("Content-Type", "application/json")
                            self.end_headers()
                            self.wfile.write(json.dumps({"challenge": challenge}).encode())
                            print(f"[ReplyServer] ✅ url_verification passed")
                            return

                        # ============ 核心：处理 card.action.trigger 回调 ============
                        event = payload.get("event", {})
                        if event.get("type") == "card.action.trigger":
                            action_obj = event.get("action", {})
                            action_value = action_obj.get("value", {})
                            # value 可能是字符串 JSON 或直接是 dict
                            if isinstance(action_value, str):
                                try:
                                    action_value = json.loads(action_value)
                                except:
                                    action_value = {}
                            action_t = action_value.get("action", "")
                            action_id = action_value.get("id", "")
                            print(f"[ReplyServer] 卡片回调: action={action_t}, id={action_id}")
                            if action_t and action_id:
                                handle_reply(action_t, action_id, self.server.server.registry)
                                status_text = '允许' if action_t == 'approve' else '拒绝'
                                result = {"code": 0, "msg": f"✅ 卡片审批完成: {status_text}"}
                                self.send_response(200)
                                self.send_header("Content-Type", "application/json")
                                self.end_headers()
                                self.wfile.write(json.dumps(result).encode())
                                return
                            elif not action_id:
                                # 无 id 则模糊匹配最新 pending
                                pending = self.server.server.pending_registry.list_pending()
                                if pending:
                                    latest_id = max(pending.keys(), key=lambda k: pending[k].get("created_at", ""))
                                    handle_reply("approve", latest_id, self.server.server.registry)
                                    result = {"code": 0, "msg": f"✅ 卡片审批完成（模糊匹配）"}
                                    self.send_response(200)
                                    self.send_header("Content-Type", "application/json")
                                    self.end_headers()
                                    self.wfile.write(json.dumps(result).encode())
                                    return

                        # 处理其他消息类型
                        if "event" in payload and isinstance(payload.get("event"), dict):
                            result = self.server.server.handle_feishu_event(event)
                        else:
                            result = self.server.server.handle_feishu_event(payload)
                            import os
                            challenge = payload.get("challenge", "")
                            expected_token = os.environ.get("FEISHU_VERIFICATION_TOKEN", "")
                            received_token = payload.get("token", "")
                            print(f"[ReplyServer] url_verification: challenge={challenge}, token={received_token}")
                            # Validate token (if env var is set)
                            if expected_token and received_token != expected_token:
                                print(f"[ReplyServer] ❌ Token mismatch! expected={expected_token}, got={received_token}")
                                self.send_response(403)
                                self.end_headers()
                                return
                            self.send_response(200)
                            self.send_header("Content-Type", "application/json")
                            self.end_headers()
                            self.wfile.write(json.dumps({"challenge": challenge}).encode())
                            print(f"[ReplyServer] ✅ url_verification passed")
                            return
                        # 处理飞书事件回调（支持多种格式）
                        # 格式1: {"event": {...}} (旧格式)
                        if "event" in payload and isinstance(payload.get("event"), dict):
                            payload = payload["event"]

                        # 格式2: 飞书卡片按钮回调（card.action.trigger 事件）
                        # 真实格式: {"event":{"type":"card.action.trigger","action":{"value":{...}}}}
                        event = payload.get("event", {})
                        if event.get("type") == "card.action.trigger":
                            action_obj = event.get("action", {})
                            action_value = action_obj.get("value", {})
                            # value 可能是字符串（JSON编码）或直接是对象
                            if isinstance(action_value, str):
                                try:
                                    action_value = json.loads(action_value)
                                except:
                                    action_value = {}
                            action_t = action_value.get("action", "")
                            action_id = action_value.get("id", "")
                            if action_t and action_id:
                                handle_reply(action_t, action_id, self.server.server.registry)
                                status_text = '允许' if action_t == 'approve' else '拒绝'
                                result = {"code": 0, "msg": f"✅ 卡片审批完成: {status_text}"}
                                self.send_response(200)
                                self.send_header("Content-Type", "application/json")
                                self.end_headers()
                                self.wfile.write(json.dumps(result).encode())
                                print(f"[ReplyServer] ✅ 卡片审批: {action_id} → {status_text}")
                                return
                            else:
                                # 按钮没有 action/id（如普通按钮），尝试模糊匹配最新pending
                                print(f"[ReplyServer] 卡片按钮无action_id，尝试模糊匹配")
                                pending = self.server.server.pending_registry.list_pending()
                                if pending:
                                    latest_id = max(pending.keys(), key=lambda k: pending[k].get("created_at", ""))
                                    handle_reply("approve", latest_id, self.server.server.registry)
                                    result = {"code": 0, "msg": f"✅ 卡片审批完成（模糊匹配）"}
                                    self.send_response(200)
                                    self.send_header("Content-Type", "application/json")
                                    self.end_headers()
                                    self.wfile.write(json.dumps(result).encode())
                                    return

                        result = self.server.server.handle_feishu_event(payload)
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps(result).encode())
                    except Exception as e:
                        print(f"[ReplyServer] 处理异常: {e}")
                        self.send_response(500)
                        self.end_headers()
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_GET(self):
                """飞书事件订阅验证（Challenge Check）"""
                import urllib.parse
                if self.path.startswith('/feishu/reply') or self.path.startswith('/feishu/approval'):
                    # 飞书发来的 challenge 验证
                    parsed = urllib.parse.urlparse(self.path)
                    params = urllib.parse.parse_qs(parsed.query)
                    challenge = params.get('challenge', [''])[0]
                    if challenge:
                        # 返回 challenge 响应（飞书要求的标准格式）
                        resp = {"challenge": challenge}
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(json.dumps(resp))))
                        self.end_headers()
                        self.wfile.write(json.dumps(resp).encode())
                        print(f"[ReplyServer] ✅ Challenge 验证成功")
                    else:
                        self.send_response(200)
                        self.send_header("Content-Type", "text/plain")
                        self.end_headers()
                        self.wfile.write(b"OK")
                    return
                self.send_response(404)
                self.end_headers()

            def log_message(self, format, *args):
                # 静默日志，避免干扰
                pass

        class ReusableTCPServer(socketserver.TCPServer):
            allow_reuse_address = True

        self._server = ReusableTCPServer(("0.0.0.0", self.port), Handler)
        self._server.server = self

        thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        thread.start()
        print(f"[ReplyServer] 🚀 HTTP Server 已启动，监听 0.0.0.0:{self.port}")
        print(f"[ReplyServer] 📡 回调地址: http://YOUR_PUBLIC_IP:{self.port}/feishu/reply")
        print(f"[ReplyServer] 💡 坤哥在飞书群回复「允许」或「拒绝」即可审批操作")


# ============ Polling 模式（备选，无公网回调时使用） ============
class ReplyPoller:
    """
    轮询飞书群组消息（无公网回调时的备选方案）
    每 5 秒检查一次飞书频道的新消息，解析审批命令
    """

    def __init__(self, registry=None, poll_interval=5):
        self.registry = registry or PendingRegistry()
        self.poll_interval = poll_interval
        self._running = False
        self._last_check = None

    def _get_recent_messages(self):
        """通过飞书 API 获取最近消息（需应用有权限）"""
        # 简化版：直接从文件/内存读取
        return []

    def poll(self):
        """单次轮询"""
        pending = self.registry.list_pending()
        if pending:
            print(f"[ReplyPoller] 当前待审批: {list(pending.keys())}")

    def start(self):
        self._running = True
        print(f"[ReplyPoller] 轮询模式已启动，间隔 {self.poll_interval} 秒")
        while self._running:
            self.poll()
            time.sleep(self.poll_interval)


# ============ 快速测试 ============
if __name__ == "__main__":
    registry = PendingRegistry()

    # 测试解析
    tests = ["允许", "拒绝", "允许 test-001", "拒绝 test-002", "允许所有", "拒绝所有"]
    print("命令解析测试:")
    for t in tests:
        action_type, action_id = parse_approval_command(t)
        print(f"  '{t}' → action={action_type}, id={action_id}")

    print()
    # 测试添加一条 pending
    registry.add("test-001", {"path": "AGENTS.md", "operation": "DELETE", "message": "删除核心文件"})

    print()
    # 测试审批
    print("审批测试:")
    handle_reply("approve", None, registry)
    print(f"  状态: {registry.get_status('test-001')}")

    print()
    # 启动 Server（注释掉，避免干扰）
    # server = ReplyServer(port=8765, registry=registry)
    # server.start()
    print("测试完成")