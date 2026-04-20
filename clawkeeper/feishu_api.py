#!/usr/bin/env python3
"""
飞书企业自建应用 API 客户端
- 获取 tenant_access_token
- 发送交互式卡片（含「允许」「拒绝」按钮）
- 接收按钮回调
"""
import os
import sys
import json
import time
import urllib.request
import urllib.parse
import threading
from datetime import datetime

# ============ 环境变量（从 /etc/environment 加载）============
import os as _os
if _os.path.exists('/etc/environment'):
    with open('/etc/environment') as _f:
        for _line in _f:
            _line = _line.strip()
            if '=' in _line and not _line.startswith('#'):
                _k, _v = _line.split('=', 1)
                _v = _v.strip('"')
                _os.environ.setdefault(_k, _v)
APP_ID = _os.environ.get("FEISHU_APP_ID", "cli_a96c9b5700f91bc9")
APP_SECRET = _os.environ.get("FEISHU_APP_SECRET", "")

# ============ Token 管理 ============
_tenant_token = {"token": None, "expires_at": 0}

def get_tenant_access_token() -> str:
    """获取 tenant_access_token（自动缓存，TTL=2小时）"""
    global _tenant_token

    if _tenant_token["token"] and time.time() < _tenant_token["expires_at"] - 60:
        return _tenant_token["token"]

    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    data = json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("code") == 0:
                _tenant_token["token"] = result["tenant_access_token"]
                _tenant_token["expires_at"] = time.time() + result.get("expire", 7200)
                return _tenant_token["token"]
            else:
                print(f"[FeishuAPI] 获取 token 失败: {result}")
                return ""
    except Exception as e:
        print(f"[FeishuAPI] Token 请求异常: {e}")
        return ""


# ============ 卡片发送 ============
def send_interactive_card(
    card: dict,
    receive_id_type: str = "user_id",
    receive_id: str = None,
    chat_id: str = None
) -> dict:
    """发送交互式卡片消息（支持用户ID或群ID）"""
    token = get_tenant_access_token()
    if not token:
        return {"code": -1, "msg": "无 token"}

    # 确定接收方
    if receive_id and receive_id_type == "user_id":
        url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=user_id"
    elif chat_id:
        url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
    else:
        return {"code": -1, "msg": "需要 receive_id 或 chat_id"}

    # 构造消息体
    message = {
        "receive_id": receive_id or chat_id,
        "msg_type": "interactive",
        "content": json.dumps(card, ensure_ascii=False)
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(message).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            return result
    except Exception as e:
        return {"code": -1, "msg": str(e)}


def build_approval_card(
    level: str,
    message: str,
    operation: str,
    details: str = "",
    pending_id: str = None
) -> dict:
    """构建审批卡片（带「允许」「拒绝」按钮）

    Args:
        level: CRITICAL/HIGH/MEDIUM
        message: 危险操作描述
        operation: 操作类型（DELETE/READ/MODIFY）
        details: 详情文本
        pending_id: 待审批ID（用于回调路由）
    """
    level_config = {
        "CRITICAL": ("🔴 最高风险告警 - 系统已终止", "red", "🔴🔴🔴"),
        "HIGH": ("🚨 高风险拦截", "orange", "🚨"),
        "MEDIUM": ("⚠️ 中风险待审核", "yellow", "⚠️"),
    }
    title, color, badge = level_config.get(level, ("📋 风险操作", "grey", "📋"))

    # 按钮回调路由（坤哥需配置公网回调地址）
    # 实际比赛中可能用 watchcat 的 http 端口做转发
    callback_url = os.environ.get(
        "FEISHU_APPROVAL_CALLBACK",
        "https://your-domain.com/feishu/approval"
    )

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"{badge} {title}"},
                "template": color
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": f"**操作**: {message}"
                },
                {
                    "tag": "markdown",
                    "content": f"**类型**: `{operation}`"
                },
                {
                    "tag": "markdown",
                    "content": f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "markdown",
                    "content": details if details else "⚠️ 请谨慎处理"
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "plain_text",
                        "content": f"🆔 审批ID: `{pending_id or 'N/A'}`"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "plain_text",
                        "content": "━━━━━━━━━━━━━━━━━━━━"
                    }
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "✅ 允许放行"},
                            "type": "primary",
                            "value": json.dumps({"action": "approve", "id": pending_id}, ensure_ascii=False)
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "❌ 拒绝"},
                            "type": "danger",
                            "value": json.dumps({"action": "reject", "id": pending_id}, ensure_ascii=False)
                        }
                    ]
                },
                {
                    "tag": "markdown",
                    "content": "💡 **CI/CAS 反黑箱审核**：操作已被拦截，AI 已暂停执行"
                }
            ]
        }
    }
    return card


# ============ 回调处理（Web Server） ============
class ApprovalServer:
    """
    轻量 HTTP Server，接收飞书按钮回调
    使用方式：ApprovalServer().start()
    """

    def __init__(self, port=8765, pending_registry=None):
        self.port = port
        self.pending_registry = pending_registry or {}
        self._server = None

    def handle_approval(self, payload: dict) -> dict:
        """处理审批回调"""
        action_data = payload.get("action_value", {})
        action_type = action_data.get("action")  # approve / reject
        pending_id = action_data.get("id")

        if not pending_id:
            return {"code": -1, "msg": "缺少审批ID"}

        # 更新 pending_registry
        if pending_id in self.pending_registry:
            entry = self.pending_registry[pending_id]
            entry["status"] = "approved" if action_type == "approve" else "rejected"
            entry["resolved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[ApprovalServer] {pending_id} → {entry['status']}")

            # 通知 interceptor（通过回调）
            if entry.get("callback"):
                try:
                    entry["callback"](entry["status"])
                except Exception as e:
                    print(f"[ApprovalServer] 回调异常: {e}")

            return {"code": 0, "status": entry["status"]}
        else:
            return {"code": -1, "msg": f"未找到审批ID: {pending_id}"}

    def start(self):
        """启动 HTTP 服务器（后台线程）"""
        import http.server
        import socketserver

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path == "/feishu/approval":
                    content_length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(content_length).decode("utf-8")

                    try:
                        payload = json.loads(body)
                        # 飞书事件回调格式
                        if "event" in payload and "action_value" in payload["event"]:
                            payload = payload["event"]

                        result = self.server.server.handle_approval(payload)

                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(json.dumps(result))))
                        self.end_headers()
                        self.wfile.write(json.dumps(result).encode())
                    except Exception as e:
                        print(f"[ApprovalServer] 处理异常: {e}")
                        self.send_response(500)
                        self.end_headers()
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format, *args):
                pass  # 静默日志

        class ReusableTCPServer(socketserver.TCPServer):
            allow_reuse_address = True

        self._server = ReusableTCPServer(("0.0.0.0", self.port), Handler)
        self._server.server = self

        thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        thread.start()
        print(f"[ApprovalServer] HTTP Server 启动，监听 0.0.0.0:{self.port}")
        print(f"[ApprovalServer] 回调地址：http://YOUR_PUBLIC_IP:{self.port}/feishu/approval")


# ============ Pending Actions 注册表 ============
class PendingRegistry:
    """
    待审批操作注册表
    interceptor 写入 → 用户点击 → server 读取并更新 → interceptor 查询结果
    """

    def __init__(self, persist_path="/root/.openclaw/workspace/.pending_actions.json"):
        self.persist_path = persist_path
        self._actions = {}
        self._callbacks = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        if os.path.exists(self.persist_path):
            try:
                with open(self.persist_path) as f:
                    self._actions = json.load(f)
            except:
                self._actions = {}

    def _save(self):
        with open(self.persist_path, 'w') as f:
            json.dump(self._actions, f, ensure_ascii=False, indent=2)

    def add(self, action_id: str, info: dict, callback=None):
        with self._lock:
            self._actions[action_id] = {
                **info,
                "status": "pending",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "resolved_at": None
            }
            self._callbacks[action_id] = callback
            self._save()
        print(f"[PendingRegistry] 新增待审批: {action_id} - {info.get('message', 'N/A')}")

    def resolve(self, action_id: str, status: str) -> dict:
        with self._lock:
            if action_id in self._actions:
                self._actions[action_id]["status"] = status
                self._actions[action_id]["resolved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                info = dict(self._actions[action_id])
                self._save()

                # 触发回调
                if action_id in self._callbacks and self._callbacks[action_id]:
                    try:
                        self._callbacks[action_id](status)
                    except:
                        pass
                return info
            return {}

    def get_status(self, action_id: str) -> str:
        return self._actions.get(action_id, {}).get("status", "unknown")

    def is_approved(self, action_id: str) -> bool:
        return self.get_status(action_id) == "approved"


if __name__ == "__main__":
    # 测试：发送卡片给坤哥
    print(f"App ID: {APP_ID}")
    print(f"App Secret: {'*' * len(APP_SECRET)}")

    # 获取 token 测试
    token = get_tenant_access_token()
    if token:
        print("✅ Token 获取成功")
    else:
        print("❌ Token 获取失败（检查 App ID/Secret）")