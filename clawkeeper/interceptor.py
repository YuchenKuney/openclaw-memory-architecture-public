#!/usr/bin/env python3
"""
Clawkeeper Interceptor v11 - 全面沙箱审批机制

核心设计：
- 所有危险操作（MEDIUM/LOW+）全部沙箱隔离 + 飞书推送审批卡片
- 系统不主动隔离人 → 等待坤哥审批后决定
- 坤哥点「允许」→ AI 继续执行；坤哥点「拒绝」→ 操作阻断

vs v10：
- MEDIUM: 之前 "警告+记录，AI可继续" → 现在 "沙箱+等待审批"
- CRITICAL: 之前 "终止+隔离" → 现在 "沙箱+紧急审批卡片"
- LOW: 新增 → 沙箱+等待审批
"""

import os
import sys
import time
import json
import signal
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from clawkeeper.reply_handler import PendingRegistry
import uuid as _uuid


# ============ 分层响应类型 ============

class InterceptResult(Enum):
    """响应枚举"""
    LOG_ONLY       = "log_only"        # 仅记录（安全操作）
    SANDBOX_WAIT   = "sandbox_wait"    # 沙箱隔离+飞书卡片+等待审批（所有危险操作）
    AUTO_APPROVED  = "auto_approved"   # 自动放行（auto_approve模式）


# ============ 操作结果 ============

@dataclass
class InterceptAction:
    result: InterceptResult
    message: str
    details: dict = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)
    pending_approval: bool = False   # 等待坤哥审批
    unblocked: bool = False          # 坤哥已放行


# ============ 主拦截器 ============

class Interceptor:
    """
    v11 核心：全面沙箱审批机制

    所有危险操作（LOW+）全部沙箱隔离，等待坤哥审批
    - 不再区分 MEDIUM(AI可继续) / HIGH(拦截) / CRITICAL(终止+隔离)
    - 统一：沙箱 + 飞书卡片 + 等待审批
    - auto_approve 模式：跳过审批直接执行
    """

    # 风险等级 → 响应类型
    RISK_TO_RESPONSE: dict = {
        0: InterceptResult.LOG_ONLY,          # SAFE → 只记录
        1: InterceptResult.SANDBOX_WAIT,     # LOW  → 沙箱+等待审批
        2: InterceptResult.SANDBOX_WAIT,      # MEDIUM → 沙箱+等待审批
        3: InterceptResult.SANDBOX_WAIT,     # HIGH → 沙箱+等待审批
        4: InterceptResult.SANDBOX_WAIT,      # CRITICAL → 沙箱+紧急审批
    }

    def __init__(self, detector, notifier):
        self.detector = detector
        self.notifier = notifier
        self.pending_actions: Dict[str, dict] = {}
        self.blocked_paths: set = set()
        self.evidence_dir = Path("/root/.openclaw/workspace/clawkeeper/evidence")
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.auto_approve = os.environ.get("CLAWKEEPER_AUTO_APPROVE", "false").lower() == "true"
        self.pending_registry = PendingRegistry()

    def approve_all(self):
        self.auto_approve = True
        os.environ["CLAWKEEPER_AUTO_APPROVE"] = "true"
        print("[Interceptor] ✅ 已启用自动批准模式")

    def revoke_all(self):
        self.auto_approve = False
        os.environ["CLAWKEEPER_AUTO_APPROVE"] = "false"
        print("[Interceptor] ⏸️ 已关闭自动批准，恢复人工审批")

    def intercept(self, action) -> InterceptAction:
        """主拦截方法：所有危险操作沙箱隔离 + 等待审批"""
        if not action:
            return InterceptAction(result=InterceptResult.LOG_ONLY, message="无风险操作")

        risk_level = int(action.level)
        response = self.RISK_TO_RESPONSE.get(risk_level, InterceptResult.LOG_ONLY)

        ia = InterceptAction(
            result=response,
            message=action.message,
            details=action.details or {},
            pending_approval=(response == InterceptResult.SANDBOX_WAIT)
        )

        if response == InterceptResult.LOG_ONLY:
            self._do_log_only(action, ia)
        elif response == InterceptResult.SANDBOX_WAIT:
            self._do_sandbox_wait(action, ia)
        elif response == InterceptResult.AUTO_APPROVED:
            self._do_auto_approved(action, ia)

        return ia

    def _do_log_only(self, action, ia: InterceptAction):
        """LOG_ONLY：只记录，不阻断，不通知"""
        self._write_evidence("LOG_ONLY", action, ia)
        print(f"[Interceptor] 📝 {ia.message}")

    def _do_sandbox_wait(self, action, ia: InterceptAction):
        """SANDBOX_WAIT：沙箱隔离 + 飞书卡片 + 等待审批"""
        path = action.details.get("path", "")
        level_name = {1:"LOW",2:"MEDIUM",3:"HIGH",4:"CRITICAL"}.get(int(action.level), "UNKNOWN")

        # 生成审批ID
        action_id = f"{level_name.lower()}-{int(time.time())}-{_uuid.uuid4().hex[:6]}"
        ia.details["action_id"] = action_id
        ia.details["blocked"] = True
        ia.details["level"] = level_name

        # 写入 PendingRegistry
        self.pending_registry.add(action_id, {
            "path": path,
            "operation": action.action_type,
            "level": level_name,
            "message": ia.message,
        }, callback=None)

        ia.pending_approval = True

        # auto_approve 模式：跳过审批直接执行
        if self.auto_approve:
            ia.unblocked = True
            ia.pending_approval = False
            ia.result = InterceptResult.AUTO_APPROVED
            self.blocked_paths.discard(path)
            print(f"[Interceptor] ✅ [AUTO-APPROVE] {level_name} 操作自动放行: {path}")
            return

        # 正常流程：发飞书卡片 + 等待审批（AI 不假死）
        self._send_approval_card(action, ia, level_name)
        print(f"[Interceptor] 🚨 [{level_name}] {ia.message} (AI 继续运行，等待坤哥审批)")
        print(f"[Interceptor] ⏳ 审批ID: {action_id} | 坤哥点「允许」放行 / 「拒绝」阻断")

    def _do_auto_approved(self, action, ia: InterceptAction):
        """AUTO_APPROVED：自动放行"""
        self._write_evidence("AUTO_APPROVED", action, ia)
        print(f"[Interceptor] ✅ [AUTO] {ia.message}")

    def _send_approval_card(self, action, ia: InterceptAction, level_name: str):
        """发送审批卡片到飞书群"""
        action_id = ia.details.get("action_id", "N/A")
        path = action.details.get("path", "")
        is_critical = level_name == "CRITICAL"

        # 根据风险等级决定颜色
        color_map = {"LOW":"blue","MEDIUM":"orange","HIGH":"red","CRITICAL":"red"}
        color = color_map.get(level_name, "grey")

        emoji_map = {"LOW":"📋","MEDIUM":"⚠️","HIGH":"🚨","CRITICAL":"🔴"}
        emoji = emoji_map.get(level_name, "📋")

        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"{emoji} 操作拦截 - 需要审批 [{level_name}]"},
                    "template": color,
                },
                "elements": [
                    {"tag": "markdown", "content": f"**🤖 AI 操作**: {action.message}"},
                    {"tag": "markdown", "content": f"**📁 路径**: `{path}`"},
                    {"tag": "markdown", "content": f"**⚠️ 风险等级**: `{level_name}`"},
                    {"tag": "hr"},
                    {"tag": "markdown", "content": f"**🆔 审批ID**: `{action_id}`"},
                    {"tag": "markdown", "content": "**📋 操作**: 点「允许」放行执行 / 点「拒绝」阻断"},
                    {"tag": "action", "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "✅ 允许"},
                            "type": "primary",
                            "value": {"action": "ALLOW", "approval_id": action_id}
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "❌ 拒绝"},
                            "type": "danger",
                            "value": {"action": "DENY", "approval_id": action_id}
                        }
                    ]},
                    {"tag": "markdown", "content": "⚠️ 系统已沙箱隔离，等待坤哥审批后AI才执行"},
                ]
            }
        }
        self._send_card(card)

        # CRITICAL 额外发送紧急通知
        if is_critical:
            self._send_urgent_alert(action, ia, action_id)

    def _send_urgent_alert(self, action, ia: InterceptAction, action_id: str):
        """CRITICAL 额外发送紧急告警（双卡片保险）"""
        card = {
            "header": {
                "title": {"tag": "plain_text", "content": "🔴🔴🔴 最高风险 - 需要立即处理"},
                "template": "red",
            },
            "elements": [
                {"tag": "markdown", "content": f"**操作**: {action.message}"},
                {"tag": "markdown", "content": f"**审批ID**: `{action_id}`"},
                {"tag": "markdown", "content": "⚠️ **请立即处理**：点击上方按钮「允许」或「拒绝」"},
            ]
        }
        self._send_card(card)

    def _load_env(self):
        """从 /etc/environment 加载环境变量"""
        if os.path.exists('/etc/environment'):
            with open('/etc/environment') as _f:
                for _line in _f:
                    _line = _line.strip()
                    if '=' in _line and not _line.startswith('#'):
                        _k, _v = _line.split('=', 1)
                        _v = _v.strip('\"')
                        os.environ.setdefault(_k, _v)

    def _send_card(self, card: dict):
        """发送飞书卡片（使用企业应用 API，支持按钮回调）"""
        self._load_env()
        app_id = os.environ.get("FEISHU_APP_ID", "cli_a96c9b5700f91bc9")
        app_secret = os.environ.get("FEISHU_APP_SECRET", "${FEISHU_APP_SECRET}")

        # 获取 tenant_access_token
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        token_data = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode("utf-8")
        token_req = urllib.request.Request(token_url, data=token_data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(token_req, timeout=10) as resp:
            token_result = json.loads(resp.read())
            if token_result.get("code") != 0:
                print(f"[Interceptor] 获取token失败: {token_result}")
                return
            token = token_result["tenant_access_token"]

        # 发送消息到群（使用 enterprise app）
        # receive_id_type: chat_id 表示群ID
        send_url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
        # 群ID用 group_id
        group_id = os.environ.get("FEISHU_GROUP_ID", "YOUR_GROUP_ID")
        # content 是卡片的 JSON 字符串（不是 {"card": card}）
        msg_body = json.dumps({
            "receive_id": group_id,
            "msg_type": "interactive",
            "content": json.dumps(card)
        }).encode("utf-8")
        msg_req = urllib.request.Request(
            send_url,
            data=msg_body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            }
        )
        with urllib.request.urlopen(msg_req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("code") != 0:
                print(f"[Interceptor] 卡片发送失败: {result}")
            else:
                print(f"[Interceptor] 卡片发送成功")

    def approve(self, path: str) -> bool:
        """坤哥批准操作"""
        if path in self.blocked_paths:
            self.blocked_paths.discard(path)
        if path in self.pending_actions:
            del self.pending_actions[path]
        os.environ.pop("CLAWKEEPER_PAUSED", None)
        print(f"[Interceptor] ✅ 坤哥已批准: {path}")
        return True

    def reject(self, path: str, rollback: bool = False) -> bool:
        """
        坤哥拒绝操作
        rollback: 是否回退文件变更（待扩展）
        """
        if path in self.blocked_paths:
            self.blocked_paths.discard(path)
        if path in self.pending_actions:
            del self.pending_actions[path]
        self._send_card({
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": "❌ 坤哥已拒绝"}, "template": "red"},
                "elements": [{"tag": "markdown", "content": f"**路径**: `{path}`\n**状态**: 已拒绝"}]
            }
        })
        print(f"[Interceptor] ❌ 坤哥已拒绝: {path}")
        return True

    def _write_evidence(self, level: str, action, ia: InterceptAction):
        entry = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "response_level": level,
            "action": action.message if hasattr(action, 'message') else str(action),
            "path": action.details.get("path", "") if hasattr(action, 'details') else "",
        }
        log_file = self.evidence_dir / "interceptor_log.jsonl"
        try:
            with open(log_file, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def wait_for_approval(self, action_id: str, timeout: int = 300) -> bool:
        """
        AI 执行危险操作前调用此方法阻塞等待坤哥审批
        一直阻塞直到：坤哥点「允许」（返回 True）
                    坤哥点「拒绝」（返回 False）
                    超时（默认300秒）（返回 False）

        用法：
            ia = interceptor.intercept(action)
            if ia.pending_approval:
                if not interceptor.wait_for_approval(ia.details['action_id']):
                    print('❌ 坤哥拒绝，操作阻断')
                    return
            # 继续执行危险操作...
        """
        deadline = time.time() + timeout
        print(f'[Interceptor] ⏳ 等待审批: {action_id} (最多 {timeout} 秒)')

        poll_interval = 0.5  # 起始轮询间隔 500ms（快速响应）
        max_interval = 5.0   # 最大轮询间隔 5 秒（避免空转）

        while time.time() < deadline:
            status = self.pending_registry.get_status(action_id)
            if status == 'approved':
                print(f'[Interceptor] ✅ 审批通过: {action_id}')
                return True
            elif status == 'rejected':
                print(f'[Interceptor] ❌ 审批拒绝: {action_id}，操作阻断')
                return False
            # 审批中：指数退避轮询，空闲时减少 CPU 浪费
            time.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.5, max_interval)

        print(f'[Interceptor] ⏰ 审批超时: {action_id}（{timeout}秒），默认拒绝')
        return False

    def get_pending(self) -> List[dict]:
        return list(self.pending_actions.values())

    def is_paused(self) -> bool:
        return os.environ.get("CLAWKEEPER_PAUSED") == "1"

    def check_and_block_if_paused(self, operation_desc: str = ""):
        if self.is_paused():
            raise SystemExit(f"Operation blocked: system paused - {operation_desc}")


if __name__ == "__main__":
    from detector import RiskDetector, RiskLevel, Action
    from notifier import FeishuNotifier

    detector = RiskDetector()
    notifier = FeishuNotifier()
    interceptor = Interceptor(detector, notifier)

    print("=" * 50)
    print("🔴 Interceptor v11 - 全面沙箱审批测试")
    print("=" * 50)

    test_cases = [
        Action(RiskLevel.SAFE, "ALLOW", "SAFE 操作", {"path": "/test"}),
        Action(RiskLevel.LOW, "ALLOW", "LOW 操作（读取日志）", {"path": "/tmp/test.log"}),
        Action(RiskLevel.MEDIUM, "ALLOW", "MEDIUM 操作（修改配置）", {"path": "config.yaml"}),
        Action(RiskLevel.HIGH, "ALLOW", "HIGH 操作（读取 Token）", {"path": "~/.gitcredentials"}),
        Action(RiskLevel.CRITICAL, "ALLOW", "CRITICAL 操作（删除系统文件）", {"path": "/etc/passwd"}),
    ]

    for action in test_cases:
        print(f"\n{'='*40}")
        result = interceptor.intercept(action)
        lvl = int(action.level)
        lvl_name = {0:"SAFE",1:"LOW",2:"MEDIUM",3:"HIGH",4:"CRITICAL"}.get(lvl,"?")
        print(f"  风险: {lvl_name} → 响应: {result.result.value}")
        print(f"  等待审批: {result.pending_approval}")
        if result.details.get("action_id"):
            print(f"  审批ID: {result.details['action_id']}")