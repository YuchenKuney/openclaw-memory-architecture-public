#!/usr/bin/env python3
"""
Demo 2: 企业机器人回调地址审批模式

实现方式：
- 飞书企业自建应用配置公网回调地址（事件订阅）
- OpenClaw ReplyServer 接收飞书回调（Flask/HTTP）
- 坤哥点击卡片按钮，飞书 POST 回调到 ReplyServer
- ReplyServer 更新注册表 + 返回 toast 提示

特点：
- 完整交互体验：卡片按钮 + toast 弹窗
- 需要公网地址 + 防火墙开放 + 飞书事件订阅配置
- 响应式：飞书主动推送，实时性强

vs Demo 1（长连接）：
- Demo 1: 轮询机制（简单但有延迟）
- Demo 2: 回调机制（实时但配置复杂）

前置条件：
1. 公网服务器（VPS）开放端口（如 8765）
2. 飞书开放平台配置回调地址（https://your-domain.com/feishu/reply）
3. 开启「卡片点击事件」订阅
"""

import os
import sys
import time
import json
import threading
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

# ============ 脱敏配置 ============
# 所有 credentials 从环境变量读取，不写死在代码里

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "cli_YOUR_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "YOUR_APP_SECRET")
FEISHU_VERIFICATION_TOKEN = os.environ.get("FEISHU_VERIFICATION_TOKEN", "YOUR_VERIFICATION_TOKEN")
FEISHU_GROUP_ID = os.environ.get("FEISHU_GROUP_ID", "oc_YOUR_GROUP_ID")

# 回调地址配置
REPLY_SERVER_HOST = os.environ.get("REPLY_SERVER_HOST", "0.0.0.0")
REPLY_SERVER_PORT = int(os.environ.get("REPLY_SERVER_PORT", "8765"))

# ============ 飞书 API ============

class FeishuAPI:
    """飞书企业自建应用 API 客户端（数据脱敏）"""

    _token = None
    _token_expire = 0

    @classmethod
    def get_tenant_access_token(cls) -> str:
        """获取 tenant access token（自动缓存2小时）"""
        if cls._token and time.time() < cls._token_expire - 60:
            return cls._token

        import urllib.request

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        data = json.dumps({
            "app_id": FEISHU_APP_ID,
            "app_secret": FEISHU_APP_SECRET
        }).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                if result.get("code") == 0:
                    cls._token = result.get("tenant_access_token", "")
                    cls._token_expire = time.time() + 7200
                    print(f"[FeishuAPI] Token 获取成功（2小时缓存）")
                    return cls._token
        except Exception as e:
            print(f"[FeishuAPI] Token 获取失败: {e}")
        return ""

    @classmethod
    def send_message(cls, chat_id: str, msg_type: str = "text", content: dict = None) -> bool:
        """发送消息到群组"""
        import urllib.request

        token = cls.get_tenant_access_token()
        if not token:
            return False

        url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
        data = json.dumps({
            "receive_id": chat_id,
            "msg_type": msg_type,
            "content": json.dumps(content, ensure_ascii=False)
        }, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        })

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                return result.get("code") == 0
        except Exception as e:
            print(f"[FeishuAPI] 消息发送失败: {e}")
            return False

    @classmethod
    def build_approval_card(cls, level: str, message: str, operation: str, pending_id: str) -> dict:
        """
        构建审批卡片（飞书 Card 消息）

        按钮 value 使用 dict 对象（非 JSON 字符串）
        这是飞书 SDK 的要求，否则回调会报 200671 错误
        """
        level_colors = {
            "LOW": "grey",
            "MEDIUM": "yellow",
            "HIGH": "red",
            "CRITICAL": "red"
        }
        level_emoji = {
            "LOW": "📋",
            "MEDIUM": "⚠️",
            "HIGH": "🚨",
            "CRITICAL": "🔴"
        }

        color = level_colors.get(level, "grey")
        emoji = level_emoji.get(level, "📋")

        return {
            "config": {"wide_screen_mode": True},
            "elements": [
                {
                    "tag": "markdown",
                    "content": f"**{emoji} 审批请求 [{level}]**\n\n🤖 **操作**: {message}\n\n🆔 **审批ID**: `{pending_id}`"
                },
                {"tag": "hr"},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"content": "✅ 允许放行", "tag": "plain_text"},
                            "type": "primary",
                            "value": {
                                "approval_id": pending_id,  # dict 对象，非字符串
                                "action": "ALLOW",
                                "risk_level": level,
                                "operation": operation
                            }
                        },
                        {
                            "tag": "button",
                            "text": {"content": "❌ 拒绝", "tag": "plain_text"},
                            "type": "danger",
                            "value": {
                                "approval_id": pending_id,
                                "action": "DENY",
                                "risk_level": level,
                                "operation": operation
                            }
                        }
                    ]
                },
                {
                    "tag": "markdown",
                    "content": "📝 **操作方法**：点击上方按钮进行审批"
                }
            ]
        }


# ============ 审批注册表 ============

PENDING_FILE = Path("/root/.openclaw/workspace/.pending_actions_demo2.json")

class ApprovalRegistry:
    """审批注册表（Demo 2 用独立文件，与生产环境隔离）"""

    def __init__(self):
        self._data = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        if PENDING_FILE.exists():
            try:
                with open(PENDING_FILE, "r") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}

    def _save(self):
        PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PENDING_FILE, "w") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def add(self, action_id: str, info: dict):
        with self._lock:
            self._data[action_id] = {
                **info,
                "status": "pending",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            self._save()
            print(f"[ApprovalRegistry] 新增待审批: {action_id} | {info.get('message', 'N/A')[:50]}")

    def resolve(self, action_id: str, status: str):
        with self._lock:
            if action_id in self._data:
                self._data[action_id]["status"] = status
                self._data[action_id]["resolved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._save()
                print(f"[ApprovalRegistry] 审批完成: {action_id} → {status}")
                return True
        return False

    def list_pending(self):
        with self._lock:
            return {k: v for k, v in self._data.items() if v.get("status") == "pending"}

    def get_status(self, action_id: str):
        with self._lock:
            return self._data.get(action_id, {}).get("status", "")


# ============ Demo 2 核心：ReplyServer（HTTP 回调服务器）============

class ReplyServer:
    """
    Demo 2 核心：飞书回调 HTTP 服务器

    工作原理：
    1. 启动 HTTP 服务器监听端口（如 8765）
    2. 飞书事件订阅配置此地址为回调 URL
    3. 坤哥点击卡片按钮 → 飞书 POST 回调到 /feishu/reply
    4. ReplyServer 解析按钮 value，更新注册表
    5. 返回 {"status_code": 0, "toast": {...}} → 飞书弹窗提示

    飞书回调格式（schema 2.0）：
    {
        "schema": "2.0",
        "header": {
            "event_type": "card.action.trigger",
            "token": "xxx"
        },
        "event": {
            "operator": {"name": "坤哥", "open_id": "ou_xxx"},
            "action": {
                "tag": "button",
                "value": {"approval_id": "xxx", "action": "ALLOW", ...}
            }
        }
    }
    """

    def __init__(self, registry: ApprovalRegistry, host: str = None, port: int = None):
        self.registry = registry
        self.host = host or REPLY_SERVER_HOST
        self.port = port or REPLY_SERVER_PORT
        self._server = None

    def handle_feishu_callback(self, payload: dict) -> dict:
        """
        处理飞书卡片回调

        返回格式（必须符合飞书规范）：
        {
            "status_code": 0,
            "status_msg": "success",
            "data": {"template_variable": {"status": "✅ 允许"}},
            "toast": {"type": "success", "content": "✅ 允许"}
        }
        """
        try:
            # 解析 schema 2.0 格式
            schema = payload.get("schema", "")
            header = payload.get("header", {})
            event = payload.get("event", {})

            # 验证 event_type
            event_type = header.get("event_type", "")
            if event_type != "card.action.trigger":
                print(f"[ReplyServer] 忽略非卡片事件: {event_type}")
                return {"status_code": 0, "status_msg": "success", "data": {}}

            # 验证 token（防止伪造）
            token = header.get("token", "")
            if token != FEISHU_VERIFICATION_TOKEN:
                print(f"[ReplyServer] ❌ Token 验证失败")
                return {"status_code": -1, "status_msg": "Token 验证失败", "data": {}}

            # 提取操作信息
            operator = event.get("operator", {})
            operator_name = operator.get("name", "未知")
            action_obj = event.get("action", {})
            value = action_obj.get("value", {})

            approval_id = value.get("approval_id", "")
            action = value.get("action", "").upper()
            risk_level = value.get("risk_level", "UNKNOWN")

            print(f"[ReplyServer] 📩 收到回调: {approval_id} | {action} | 操作人: {operator_name}")

            # 解析审批结果
            if action == "ALLOW":
                self.registry.resolve(approval_id, "approved")
                status_text = "允许"
                return {
                    "status_code": 0,
                    "status_msg": "success",
                    "data": {"template_variable": {"status": f"✅ {status_text}"}},
                    "toast": {"type": "success", "content": f"✅ {status_text}"}
                }
            elif action == "DENY":
                self.registry.resolve(approval_id, "rejected")
                status_text = "拒绝"
                return {
                    "status_code": 0,
                    "status_msg": "success",
                    "data": {"template_variable": {"status": f"❌ {status_text}"}},
                    "toast": {"type": "error", "content": f"❌ {status_text}"}
                }

            return {"status_code": 0, "status_msg": "success", "data": {}}

        except Exception as e:
            print(f"[ReplyServer] 处理回调异常: {e}")
            return {"status_code": -1, "status_msg": str(e), "data": {}}

    def handle_url_verification(self, payload: dict) -> dict:
        """
        处理飞书 URL 验证（配置回调地址时，飞书会发送验证请求）

        请求格式：
        {"type": "url_verification", "challenge": "xxx", "token": "yyy"}

        响应格式（必须原样返回 challenge）：
        {"challenge": "xxx"}
        """
        challenge = payload.get("challenge", "")
        print(f"[ReplyServer] URL 验证: challenge={challenge}")
        return {"challenge": challenge}

    def start(self):
        """启动 HTTP 服务器"""
        self._server = HTTPServer((self.host, self.port), self._make_handler())
        print(f"[ReplyServer] 🚀 HTTP 服务器启动: http://{self.host}:{self.port}")
        print(f"[ReplyServer] 回调地址: http://YOUR_PUBLIC_IP:{self.port}/feishu/reply")
        self._server.serve_forever()

    def _make_handler(self):
        """动态创建请求处理器（捕获 self）"""
        registry = self.registry
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                # 减少日志噪音
                if "favicon" not in args[0]:
                    print(f"[HTTP] {args[0]}")

            def do_GET(self):
                """处理 GET 请求（健康检查、URL 验证）"""
                if self.path.startswith("/feishu/reply"):
                    # URL 验证（飞书配置回调地址时发送）
                    parsed = urllib.parse.urlparse(self.path)
                    params = urllib.parse.parse_qs(parsed.query)
                    if "challenge" in params:
                        challenge = params["challenge"][0]
                        print(f"[ReplyServer] URL 验证: challenge={challenge}")
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"challenge": challenge}).encode())
                        return

                # 健康检查
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"OK")

            def do_POST(self):
                """处理 POST 请求（飞书回调）"""
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8")

                try:
                    payload = json.loads(body)
                except Exception as e:
                    print(f"[ReplyServer] JSON 解析失败: {e}")
                    self.send_error(400, "Invalid JSON")
                    return

                # URL 验证
                if payload.get("type") == "url_verification":
                    result = server.handle_url_verification(payload)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(result).encode())
                    return

                # 卡片回调
                if self.path.startswith("/feishu/reply"):
                    result = server.handle_feishu_callback(payload)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(result, ensure_ascii=False).encode())
                    return

                # 其他路径
                self.send_error(404, "Not Found")

        return Handler

    def stop(self):
        """停止服务器"""
        if self._server:
            self._server.shutdown()
            print("[ReplyServer] ⏹️ HTTP 服务器已停止")


# ============ Demo 2 演示场景 ============

def send_approval_card(level: str, message: str, operation: str, action_id: str) -> bool:
    """发送审批卡片到飞书群"""
    card = FeishuAPI.build_approval_card(level, message, operation, action_id)
    content = card  # Card 格式不需要 msg_type

    success = FeishuAPI.send_message(FEISHU_GROUP_ID, "interactive", content)
    if success:
        print(f"[Demo2] ✅ 审批卡片已发送: {action_id}")
    return success


def demo_approval_scenario():
    """
    Demo 2 场景：模拟 AI 执行危险操作 → 发送审批卡片 → 等待按钮回调

    流程：
    1. AI 要执行危险操作（删除文件）
    2. 发送带按钮的审批卡片到飞书群
    3. 坤哥点击「✅ 允许放行」按钮
    4. 飞书 POST 回调到 ReplyServer
    5. ReplyServer 更新注册表 + 返回 toast 弹窗
    6. wait_for_approval() 收到结果，AI 继续执行

    前置条件：
    1. ReplyServer 公网可达（防火墙开放 8765）
    2. 飞书开放平台配置回调地址
    3. 开启「卡片点击事件」订阅
    """
    print("=" * 60)
    print("🔴 Demo 2: 企业机器人回调地址审批模式")
    print("=" * 60)
    print()
    print("📋 场景：AI 要执行危险操作（删除测试文件）")
    print("🔧 触发：点击卡片中的「✅ 允许放行」按钮")
    print()
    print("步骤：")
    print("  1. ReplyServer 已启动，监听回调")
    print("  2. 飞书群收到带按钮的审批卡片")
    print("  3. 坤哥点击「✅ 允许放行」")
    print("  4. 飞书 POST 回调 → ReplyServer")
    print("  5. 飞书弹出 toast 提示「✅ 允许」")
    print("  6. wait_for_approval() 收到结果")
    print()
    print("=" * 60)

    # 初始化
    registry = ApprovalRegistry()
    action_id = f"demo2-{int(time.time())}"
    action_message = "[DEMO] 删除测试文件 /tmp/demo2_test.txt"

    # 添加到待审批
    registry.add(action_id, {
        "path": "/tmp/demo2_test.txt",
        "operation": "DELETE",
        "level": "HIGH",
        "message": action_message,
    })

    # 发送审批卡片
    send_approval_card("HIGH", action_message, "DELETE", action_id)

    print()
    print(f"⏳ 等待坤哥点击卡片按钮...")
    print(f"   审批ID: {action_id}")
    print()

    # 阻塞等待（最多300秒）
    deadline = time.time() + 300
    check_count = 0
    print(f"[Demo2] ⏳ 等待审批: {action_id} (最多 300 秒)")
    print(f"[Demo2] 📋 等待方式: ReplyServer 接收飞书卡片回调")
    print(f"[Demo2] 💡 坤哥操作: 点击卡片中的「✅ 允许放行」按钮")
    print("-" * 60)

    while time.time() < deadline:
        check_count += 1
        elapsed = int(time.time() - (deadline - 300))
        status = registry.get_status(action_id)

        if status == "approved":
            print(f"[Demo2] ✅ 审批通过！（ReplyServer 已收到回调）")
            return True
        elif status == "rejected":
            print(f"[Demo2] ❌ 审批拒绝！（ReplyServer 已收到回调）")
            return False
        else:
            if check_count % 5 == 1:
                print(f"[Demo2] ⏳ 等待中... (每2秒检查一次，已等 {elapsed}/300 秒)")

        time.sleep(2)

    print(f"[Demo2] ⏰ 审批超时（300秒），默认拒绝")
    return False


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║               Demo 2: 回调地址审批模式                        ║
╠══════════════════════════════════════════════════════════════╣
║  原理：公网回调地址 + 飞书事件订阅                            ║
║                                                            ║
║  前置条件：                                                 ║
║    1. 公网服务器（VPS）开放端口                             ║
║    2. 飞书开放平台配置回调地址                              ║
║    3. 开启「卡片点击事件」订阅                              ║
║                                                            ║
║  交互流程：                                                 ║
║    1. 运行此脚本（自动启动 ReplyServer）                    ║
║    2. 飞书群收到带按钮的审批卡片                            ║
║    3. 坤哥点击「✅ 允许放行」                               ║
║    4. 飞书弹出 toast 提示「✅ 允许」                        ║
║                                                            ║
║  对比 Demo 1（长连接）：                                    ║
║    Demo 1: 轮询机制（简单但有5秒延迟）                      ║
║    Demo 2: 回调机制（实时+toast弹窗）                       ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # 初始化组件
    registry = ApprovalRegistry()
    server = ReplyServer(registry, host="0.0.0.0", port=8765)

    # 启动 ReplyServer（后台线程）
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()

    print()
    print("🚀 ReplyServer 已启动，监听 http://0.0.0.0:8765")
    print()

    # 发送第一个测试卡片
    action_id = f"demo2-init-{int(time.time())}"
    registry.add(action_id, {
        "operation": "TEST",
        "level": "HIGH",
        "message": "[Demo2 初始化测试] 点击下方按钮进行验收"
    })
    send_approval_card("HIGH", "[Demo2 初始化测试] 点击下方按钮进行验收", "TEST", action_id)

    print()
    print("📋 初始化卡片已发送，点击按钮测试回调链路...")
    print("   按 Ctrl+C 停止")
    print()

    # 保持运行
    try:
        while True:
            time.sleep(10)
            pending = registry.list_pending()
            if pending:
                for aid, info in pending.items():
                    print(f"📋 待审批: {aid} | {info.get('message', '')[:50]}")
    except KeyboardInterrupt:
        server.stop()
        print("\n👋 Demo 2 结束")