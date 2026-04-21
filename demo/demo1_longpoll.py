#!/usr/bin/env python3
"""
Demo 1: 企业机器人长连接审批模式

实现方式：
- 飞书企业自建应用接收群组消息（@机器人触发）
- OpenClaw 内置飞书消息监听（长连接轮询）
- 坤哥在群里 @子agent + 发送「允许/拒绝」完成审批

特点：
- 简单：只需要飞书 API 权限（读取消息）
- 实时：OpenClaw 主 session 处理
- 限制：只能在群里 @子agent

vs Demo 2（回调地址）：
- Demo 2 支持卡片按钮点击（完整交互体验）
- Demo 1 只能文字命令审批（简单直接）
"""

import os
import sys
import time
import json
import threading
from datetime import datetime
from pathlib import Path

# 脱敏：所有 credentials 从环境变量读取，不写死在代码里
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "cli_YOUR_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "YOUR_APP_SECRET")
FEISHU_GROUP_ID = os.environ.get("FEISHU_GROUP_ID", "oc_YOUR_GROUP_ID")
FEISHU_APPROVAL_BOT_NAME = os.environ.get("FEISHU_APPROVAL_BOT_NAME", "审批机器人")

# ============ 飞书 API 工具 ============

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
        import urllib.error

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
    def get_messages(cls, chat_id: str, start_time: int = None, page_size: int = 50) -> list:
        """获取群组最近消息（用于审批命令检测）"""
        import urllib.request

        token = cls.get_tenant_access_token()
        if not token:
            return []

        # 转换时间戳（毫秒）
        if start_time is None:
            start_time = int((time.time() - 300) * 1000)  # 最近5分钟

        url = f"https://open.feishu.cn/open-apis/im/v1/messages?container_id_type=chat&container_id={chat_id}&start_time={start_time}&page_size={page_size}&sort_type=ByCreateTimeDesc"

        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                if result.get("code") == 0:
                    items = result.get("data", {}).get("items", [])
                    return items
        except Exception as e:
            print(f"[FeishuAPI] 消息获取失败: {e}")
        return []


# ============ 审批注册表 ============

PENDING_FILE = Path("/root/.openclaw/workspace/.pending_actions_demo.json")

class ApprovalRegistry:
    """审批注册表（Demo 用独立文件，与生产环境隔离）"""

    def __init__(self):
        self._data = {}
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
        self._data[action_id] = {
            **info,
            "status": "pending",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._save()
        print(f"[ApprovalRegistry] 新增待审批: {action_id} | {info.get('message', 'N/A')[:50]}")

    def resolve(self, action_id: str, status: str):
        if action_id in self._data:
            self._data[action_id]["status"] = status
            self._data[action_id]["resolved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._save()
            print(f"[ApprovalRegistry] 审批完成: {action_id} → {status}")
            return True
        return False

    def list_pending(self):
        return {k: v for k, v in self._data.items() if v.get("status") == "pending"}

    def get_status(self, action_id: str):
        return self._data.get(action_id, {}).get("status", "")


# ============ 审批命令解析 ============

def parse_approval_command(text: str) -> tuple:
    """
    解析审批命令
    返回: (action_type: approve/reject, action_id: str or None)
    """
    text = text.strip()

    # 直接命令
    if text in ("允许", "通过", "yes", "✅", "好", "同意"):
        return ("approve", None)
    if text in ("拒绝", "否决", "no", "❌", "不行", "不同意"):
        return ("reject", None)

    # 带 ID 命令
    if text.startswith("允许 ") or text.startswith("通过 "):
        parts = text.split(" ", 1)
        return ("approve", parts[1].strip() if len(parts) > 1 else None)
    if text.startswith("拒绝 ") or text.startswith("否决 "):
        parts = text.split(" ", 1)
        return ("reject", parts[1].strip() if len(parts) > 1 else None)

    # 纯 ID（作为 approve）
    if text.startswith("action-") or text.startswith("high-") or text.startswith("critical-"):
        return ("approve", text.strip())

    return (None, None)


# ============ Demo 1 核心：长连接审批监听 ============

class ApprovalListener:
    """
    Demo 1 核心：长连接审批监听器

    工作原理：
    - 每 5 秒轮询飞书群组消息
    - 检测 @审批机器人 的消息
    - 解析「允许」「拒绝」等命令
    - 更新审批注册表
    """

    def __init__(self, group_id: str = None, bot_name: str = None):
        self.group_id = group_id or FEISHU_GROUP_ID
        self.bot_name = bot_name or FEISHU_APPROVAL_BOT_NAME
        self.registry = ApprovalRegistry()
        self._last_check_time = int((time.time() - 60) * 1000)  # 初始：最近1分钟
        self._running = False
        self._thread = None

    def send_approval_request(self, action_id: str, message: str, level: str = "HIGH") -> bool:
        """发送审批请求到飞书群"""
        level_emoji = {"LOW": "📋", "MEDIUM": "⚠️", "HIGH": "🚨", "CRITICAL": "🔴"}
        emoji = level_emoji.get(level, "📋")

        content = {
            "text": f"""{emoji} **审批请求 [{level}]**

🤖 操作: {message}
🆔 审批ID: `{action_id}`

回复示例：
• 「允许」- 放行操作
• 「拒绝」- 阻断操作
• 「允许 {action_id}」- 精确指定

---"""
        }

        success = FeishuAPI.send_message(self.group_id, "post", content)
        if success:
            print(f"[ApprovalListener] 审批请求已发送: {action_id}")
        return success

    def process_message(self, msg: dict) -> bool:
        """处理单条消息，检测审批命令"""
        try:
            # 提取消息内容
            msg_type = msg.get("msg_type", "")
            body = msg.get("body", {})
            content_str = body.get("content", "{}")

            # 解析文本消息
            if msg_type == "text":
                content = json.loads(content_str)
                text = content.get("text", "").strip()

                # 检测是否 @机器人
                if f"@{self.bot_name}" not in text and f"@{self.bot_name.replace('审批机器人','')}" not in text:
                    return False

                # 解析审批命令
                action_type, action_id = parse_approval_command(text)
                if not action_type:
                    return False

                # 获取审批人信息
                sender = msg.get("sender", {})
                sender_name = sender.get("sender_name", "未知")

                print(f"[ApprovalListener] 📩 收到审批命令: {action_type} | from {sender_name}")

                # 处理模糊命令（无 action_id）
                if not action_id:
                    pending = self.registry.list_pending()
                    if pending:
                        # 取最新的
                        action_id = max(pending.keys(), key=lambda k: pending[k].get("created_at", ""))
                        print(f"[ApprovalListener] 模糊匹配到: {action_id}")
                    else:
                        print(f"[ApprovalListener] ❌ 无待审批项")
                        FeishuAPI.send_message(
                            self.group_id, "text",
                            {"text": "❌ 当前没有待审批的操作"}
                        )
                        return False

                # 执行审批
                if self.registry.resolve(action_id, "approved" if action_type == "approve" else "rejected"):
                    status_text = "✅ 已允许" if action_type == "approve" else "❌ 已拒绝"
                    FeishuAPI.send_message(
                        self.group_id, "text",
                        {"text": f"{status_text} | ID: {action_id}\n来自: {sender_name}"}
                    )
                    return True
                else:
                    FeishuAPI.send_message(
                        self.group_id, "text",
                        {"text": f"❌ 未找到审批项: {action_id}"}
                    )
                    return False

        except Exception as e:
            print(f"[ApprovalListener] 消息处理异常: {e}")
        return False

    def poll(self):
        """轮询飞书群消息"""
        messages = FeishuAPI.get_messages(self.group_id, self._last_check_time)
        if messages:
            # 更新检查时间（取最新消息时间）
            self._last_check_time = int(messages[0].get("create_time", self._last_check_time)) + 1
            # 按时间顺序处理（从旧到新）
            for msg in reversed(messages):
                self.process_message(msg)

    def start(self):
        """启动长连接监听"""
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print(f"[ApprovalListener] 🚀 长连接监听已启动（每5秒轮询）")
        print(f"[ApprovalListener] 👥 监听群组: {self.group_id}")
        print(f"[ApprovalListener] 🤖 机器人名称: {self.bot_name}")

    def stop(self):
        """停止监听"""
        self._running = False
        print("[ApprovalListener] ⏹️ 监听已停止")

    def _run(self):
        """后台轮询循环"""
        while self._running:
            try:
                self.poll()
            except Exception as e:
                print(f"[ApprovalListener] 轮询异常: {e}")
            time.sleep(5)

    def wait_for_approval(self, action_id: str, timeout: int = 300) -> bool:
        """
        Demo 1 核心：阻塞等待审批（供 demo 场景使用）

        用法：
            listener = ApprovalListener()
            listener.add_pending(action_id, {...})
            listener.send_approval_request(...)
            result = listener.wait_for_approval(action_id)
            if result:
                print("✅ 审批通过，继续执行")
            else:
                print("❌ 审批拒绝/超时，阻断操作")
        """
        deadline = time.time() + timeout
        check_count = 0
        print(f"[ApprovalListener] ⏳ 等待审批: {action_id} (最多 {timeout} 秒)")
        print(f"[ApprovalListener] 📋 等待方式: 每2秒检查一次飞书群消息")
        print(f"[ApprovalListener] 💡 坤哥操作: 在飞书群 @审批机器人 + 发送「允许」")
        print("-" * 60)

        while time.time() < deadline:
            check_count += 1
            elapsed = int(time.time() - (deadline - timeout))
            status = self.registry.get_status(action_id)
            
            if status == "approved":
                print(f"[ApprovalListener] ✅ 审批通过！（检查了 {check_count} 次）")
                return True
            elif status == "rejected":
                print(f"[ApprovalListener] ❌ 审批拒绝！（检查了 {check_count} 次）")
                return False
            else:
                # 每10秒打印一次等待状态（避免刷屏）
                if check_count % 5 == 1:
                    print(f"[ApprovalListener] ⏳ 等待中... (第 {check_count} 次检查，已等 {elapsed}/{timeout} 秒)")
            
            time.sleep(2)

        print(f"[ApprovalListener] ⏰ 审批超时（300秒），默认拒绝")
        return False

        print(f"[ApprovalListener] ⏰ 审批超时: {action_id}（{timeout}秒），默认拒绝")
        return False


# ============ Demo 1 演示场景 ============

def demo_approval_scenario():
    """
    Demo 1 场景：模拟 AI 执行危险操作 → 发送审批请求 → 等待审批

    流程：
    1. AI 要执行危险操作（删除文件）
    2. 发送审批请求到飞书群
    3. 坤哥在群里 @审批机器人 + 回复「允许」
    4. 监听器检测到命令，更新注册表
    5. wait_for_approval() 收到结果，AI 继续执行

    坤哥操作步骤：
    1. 启动此脚本
    2. 在飞书群 @审批机器人 + 发送「允许」
    3. 观察审批链路
    """
    print("=" * 60)
    print("🔴 Demo 1: 企业机器人长连接审批模式")
    print("=" * 60)
    print()
    print("📋 场景：AI 要执行危险操作（删除测试文件）")
    print("🔧 触发：在飞书群 @审批机器人 + 回复「允许」")
    print()
    print("步骤：")
    print("  1. 启动监听器（后台轮询飞书群消息）")
    print("  2. 模拟 AI 发送审批请求到群")
    print("  3. 坤哥在群里 @审批机器人 + 「允许」")
    print("  4. 监听器收到命令，更新注册表")
    print("  5. wait_for_approval() 收到结果")
    print()
    print("=" * 60)

    # 初始化监听器
    listener = ApprovalListener()

    # 模拟危险操作
    action_id = f"demo-{int(time.time())}"
    action_message = "[DEMO] 删除测试文件 /tmp/demo_test.txt"

    # 添加到待审批
    listener.registry.add(action_id, {
        "path": "/tmp/demo_test.txt",
        "operation": "DELETE",
        "level": "HIGH",
        "message": action_message,
    })

    # 发送审批请求到群
    listener.send_approval_request(action_id, action_message, "HIGH")

    print()
    print(f"⏳ 等待坤哥在飞书群审批（@审批机器人 + 「允许」）...")
    print(f"   审批ID: {action_id}")
    print()

    # 阻塞等待（最多300秒）
    result = listener.wait_for_approval(action_id, timeout=300)

    print()
    if result:
        print("✅ 审批通过！AI 继续执行危险操作...")
    else:
        print("❌ 审批拒绝/超时！AI 阻断危险操作")

    return result


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║                Demo 1: 长连接审批模式                        ║
╠══════════════════════════════════════════════════════════════╣
║  原理：OpenClaw 每5秒轮询飞书群消息，检测@审批命令            ║
║                                                            ║
║  坤哥操作：                                                 ║
║    1. 运行此脚本                                             ║
║    2. 飞书群收到审批卡片                                     ║
║    3. @审批机器人 + 发送「允许」                             ║
║    4. 观察审批结果                                           ║
║                                                            ║
║  对比 Demo 2（回调地址）：                                   ║
║    Demo 1: 文字命令审批（简单）                              ║
║    Demo 2: 卡片按钮+toast弹窗（完整交互体验）                 ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # 启动长连接监听（后台）
    listener = ApprovalListener()
    listener.start()

    print()
    print("🚀 监听器已启动，每5秒轮询一次飞书群消息")
    print()

    # 等待坤哥在群里发送命令（阻塞）
    try:
        while True:
            time.sleep(10)
            pending = listener.registry.list_pending()
            if pending:
                for aid, info in pending.items():
                    print(f"📋 待审批: {aid} | {info.get('message', '')[:50]}")
    except KeyboardInterrupt:
        listener.stop()
        print("\n👋 Demo 1 结束")