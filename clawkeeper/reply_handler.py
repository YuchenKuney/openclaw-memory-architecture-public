from __future__ import annotations
#!/usr/bin/env python3
"""
Clawkeeper ReplyHandler - 飞书审批回调处理器

v11.2: 支持飞书 schema 2.0 真实回调格式
{
  "schema": "2.0",
  "header": {
    "event_type": "card.action.trigger",
    "token": "verification_token"
  },
  "event": {
    "operator": {"user_id": "...", "name": "坤哥"},
    "context": {"open_chat_id": "oc_xxx"},
    "action": {
      "tag": "button",
      "value": {"approval_id": "...", "action": "ALLOW", "risk_level": "HIGH", "path": "..."}
    }
  }
}
"""

import os
import json

import urllib.request
import urllib.error
import time

import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# 全局 registry 引用（由 start() 时设置）
_g_registry = None


# ============ HTTP Server（内嵌在类里） ============

class ReplyServer:
    """飞书卡片回调 HTTP Server"""

    def __init__(self, port: int = 8765, registry: PendingRegistry = None):
        global _g_registry
        self.port = port
        self.registry = registry or PendingRegistry()
        _g_registry = self.registry
        self._server = None

    def start(self):
        """启动 HTTP Server（阻塞）"""
        import http.server
        import socketserver

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                global _g_registry
                if self.path not in ("/feishu/reply", "/feishu/approval"):
                    self.send_response(404)
                    self.end_headers()
                    return

                try:
                    content_length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(content_length).decode("utf-8")
                    payload = json.loads(body)

                    print(f"[ReplyServer] POST {self.path} | schema={payload.get('schema','?')} event_type={payload.get('header',{}).get('event_type','?')}")

                    # ============ 1. url_verification ============
                    if payload.get("type") == "url_verification":
                        challenge = payload.get("challenge", "")
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"challenge": challenge}).encode())
                        print(f"[ReplyServer] ✅ url_verification: {challenge}")
                        return

                    # ============ 2. schema 2.0 card.action.trigger ============
                    header = payload.get("header", {})
                    event = payload.get("event", {})

                    if payload.get("schema") == "2.0" and header.get("event_type") == "card.action.trigger":
                        action_obj = event.get("action", {})
                        action_value = action_obj.get("value", {})
                        operator = event.get("operator", {})
                        context = event.get("context", {})

                        approval_id = action_value.get("approval_id", "")
                        action_t = action_value.get("action", "")  # "ALLOW" or "DENY"
                        risk_level = action_value.get("risk_level", "")
                        path = action_value.get("path", "")
                        operator_name = operator.get("name", "坤哥")
                        chat_id = context.get("open_chat_id", "")

                        print(f"[ReplyServer] 📩 卡片回调: op={operator_name} action={action_t} id={approval_id} level={risk_level}")

                        if approval_id:
                            if action_t.upper() == "ALLOW":
                                handle_reply("approve", approval_id, _g_registry)
                                status_text = "允许"
                            elif action_t.upper() == "DENY":
                                handle_reply("reject", approval_id, _g_registry)
                                status_text = "拒绝"
                            else:
                                pending = _g_registry.list_pending()
                                if pending:
                                    latest_id = max(pending.keys(), key=lambda k: pending[k].get("created_at", ""))
                                    handle_reply("approve", latest_id, _g_registry)
                                    status_text = "允许（模糊）"
                                else:
                                    status_text = "无待审批项"

                            result = {"status_code": 0, "status_msg": "success", "data": {"template_variable": {"status": "✅ " + status_text}}, "toast": {"type": "success", "content": "✅ " + status_text}}
                            self.send_response(200)
                            self.send_header("Content-Type", "application/json")
                            self.end_headers()
                            self.wfile.write(json.dumps(result).encode())
                            print(f"[ReplyServer] ✅ 响应: {status_text}")
                            return
                        else:
                            print(f"[ReplyServer] ⚠️ 无 approval_id: {action_value}")

                    # ============ 3. 旧格式 card.action.trigger ============
                    event_type = event.get("type", "")
                    if event_type == "card.action.trigger":
                        action_obj = event.get("action", {})
                        action_value = action_obj.get("value", {})
                        if isinstance(action_value, str):
                            try:
                                action_value = json.loads(action_value)
                            except:
                                action_value = {}
                        action_t = action_value.get("action", "")
                        action_id = action_value.get("id", "")
                        if action_t and action_id:
                            handle_reply(action_t, action_id, _g_registry)
                            result = {"code": 0, "msg": f"✅ 卡片审批完成"}
                        else:
                            result = {"status_code": 0, "status_msg": "success", "data": {}, "toast": {"type": "success", "content": "已处理"}}
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps(result).encode())
                        return

                    # ============ 4. 其他消息类型 ============
                    # 尝试用 handle_feishu_event
                    if hasattr(self.server, 'server') and hasattr(self.server.server, 'handle_feishu_event'):
                        result = self.server.server.handle_feishu_event(event if event else payload)
                    else:
                        result = {"status_code": 0, "status_msg": "success", "data": {}, "toast": {"type": "success", "content": "已处理"}}

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(result).encode())

                except Exception as e:
                    print(f"[ReplyServer] 处理异常: {e}")
                    self.send_response(500)
                    self.end_headers()

            def do_GET(self):
                """飞书事件订阅 Challenge 验证"""
                if self.path.startswith("/feishu/reply") or self.path.startswith("/feishu/approval"):
                    import urllib.parse
                    parsed = urllib.parse.urlparse(self.path)
                    params = urllib.parse.parse_qs(parsed.query)
                    challenge = params.get("challenge", [""])[0]
                    if challenge:
                        resp = {"challenge": challenge}
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps(resp).encode())
                        print(f"[ReplyServer] ✅ GET challenge: {challenge}")
                        return
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"OK")

            def log_message(self, format, *args):
                pass

        class ReuseAddrTCPServer(socketserver.TCPServer):
            allow_reuse_address = True

        self._server = ReuseAddrTCPServer(("", self.port), Handler)
        self._server.server = self  # 让 Handler 能访问 ReplyServer 实例
        print(f"[ReplyServer] 🚀 HTTP Server 已启动，监听 0.0.0.0:{self.port}")
        print(f"[ReplyServer] 📡 回调地址: http://YOUR_PUBLIC_IP:{self.port}/feishu/reply")
        self._server.serve_forever()


# ============ 文件注册表（与 interceptor 共享） ============

PENDING_FILE = "/root/.openclaw/workspace/.pending_actions.json"


class PendingRegistry:
    """轻量级待审批注册表（文件共享，interceptor 和 reply_handler 共用）"""

    def __init__(self, filepath: str = None):
        self.filepath = filepath or PENDING_FILE
        self._data = {}
        self._callbacks = {}
        self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}

    def _save(self):
        Path(self.filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(self.filepath, "w") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def add(self, action_id: str, info: dict, callback=None):
        self._data[action_id] = {
            **info,
            "status": "pending",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._callbacks[action_id] = callback
        self._save()
        print(f"[PendingRegistry] 新增待审批: {action_id} | {info.get('message', info.get('path', 'N/A'))}")

    def resolve(self, action_id: str, status: str) -> dict:
        # 每次处理前重新加载文件，确保拿到最新数据（多实例共享）
        self._load()
        if action_id not in self._data:
            # 模糊匹配最新 pending
            pending = [k for k, v in self._data.items() if v.get("status") == "pending"]
            if pending:
                action_id = pending[-1]
                print(f"[PendingRegistry] 模糊匹配到: {action_id}")
            else:
                print(f"[PendingRegistry] ❌ 未找到: {action_id}")
                return {}

        if action_id in self._data:
            self._data[action_id]["status"] = status
            self._data[action_id]["resolved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            info = dict(self._data[action_id])
            self._save()
            print(f"[PendingRegistry] ✅ 审批完成: {action_id} → {status}")

            if action_id in self._callbacks and self._callbacks[action_id]:
                try:
                    self._callbacks[action_id](status, action_id, info)
                except Exception as e:
                    print(f"[PendingRegistry] 回调异常: {e}")

            return info
        return {}

    def list_pending(self) -> dict:
        return {k: v for k, v in self._data.items() if v.get("status") == "pending"}

    def get_status(self, action_id: str) -> str:
        return self._data.get(action_id, {}).get("status", "")


# ============ 命令解析（从飞书文字消息） ============

def parse_approval_command(text: str) -> tuple:
    """解析坤哥的审批命令"""
    text = text.strip()
    if text in ("允许", "通过", "yes", "✅", "好的", "同意"):
        return ("approve", None)
    if text in ("拒绝", "否决", "no", "❌", "不行", "不同意"):
        return ("reject", None)
    if text.startswith("允许 ") or text.startswith("通过 "):
        parts = text.split(" ", 1)
        return ("approve", parts[1] if len(parts) > 1 else None)
    if text.startswith("拒绝 ") or text.startswith("否决 "):
        parts = text.split(" ", 1)
        return ("reject", parts[1] if len(parts) > 1 else None)
    # 不带 action 的纯 ID
    if text.startswith("action-") or text.startswith("high-") or text.startswith("critical-"):
        return ("approve", text)
    return (None, None)


def handle_reply(action_type: str, action_id: str, registry: PendingRegistry):
    status = "approved" if action_type == "approve" else "rejected"
    registry.resolve(action_id, status)


if __name__ == "__main__":
    registry = PendingRegistry()
    server = ReplyServer(port=8765, registry=registry)
    print("启动 ReplyServer...")
    server.start()