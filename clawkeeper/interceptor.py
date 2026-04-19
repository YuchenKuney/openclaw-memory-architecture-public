#!/usr/bin/env python3
"""
Clawkeeper Interceptor - 操作拦截器

PR② 核心：分层响应机制
根据 RiskLevel 决定响应深度：
- LOW      → LOG_ONLY      ：仅记录到日志，不阻断
- MEDIUM   → WARN_AND_LOG  ：记录 + 飞书告警，AI 可继续
- HIGH     → BLOCK_AND_NOTIFY：拦截 + 飞书立即通知 + 等待人工审批
- CRITICAL → KILL_AND_ISOLATE：终止 + 进程隔离 + 证据取证 + 飞书紧急告警

配合 PR① 双层检测：
  - 正则 HIGH+ → 绕过语义判断，直接触发 BLOCK/KILL
  - 语义升级到 HIGH → 触发 BLOCK_AND_NOTIFY
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


# ============ 分层响应类型 ============

class InterceptResult(Enum):
    """PR② 核心：分层响应枚举"""
    LOG_ONLY       = "log_only"        # 仅记录
    WARN_AND_LOG   = "warn_and_log"    # 警告+记录
    BLOCK_AND_NOTIFY = "block_and_notify"  # 拦截+飞书通知
    KILL_AND_ISOLATE = "kill_and_isolate"  # 终止+隔离+取证


# ============ 分层响应结果 ============

@dataclass
class InterceptAction:
    """PR② 核心数据结构：带响应等级的操作结果"""
    result: InterceptResult
    message: str
    details: dict = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)  # 取证数据
    pending_approval: bool = False   # 是否需要人工审批
    unblocked: bool = False          # 坤哥是否已放行


# ============ 主拦截器 ============

class Interceptor:
    """
    PR② 核心：分层响应拦截器

    设计原则：
    - 不再是"检测到就杀"，而是按风险等级梯度响应
    - 所有操作都有日志，误杀后可审计
    - HIGH+ 操作必须人工审批，避免自动拦截导致的业务中断
    """

    # 风险等级 → 响应类型 映射表（PR② 核心逻辑）
    RISK_TO_RESPONSE: dict = {
        # RiskLevel value → InterceptResult
        0: InterceptResult.LOG_ONLY,        # SAFE → 只记录
        1: InterceptResult.LOG_ONLY,        # LOW  → 只记录
        2: InterceptResult.WARN_AND_LOG,    # MEDIUM → 警告+记录
        3: InterceptResult.BLOCK_AND_NOTIFY, # HIGH → 拦截+通知
        4: InterceptResult.KILL_AND_ISOLATE, # CRITICAL → 终止+隔离
    }

    def __init__(self, detector, notifier):
        self.detector = detector
        self.notifier = notifier
        self.pending_actions: Dict[str, dict] = {}   # 待审核操作 {path: info}
        self.blocked_paths: set = set()               # 被拦截的路径
        self.evidence_dir = Path("/root/.openclaw/workspace/clawkeeper/evidence")
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        # PR⑥ 新增：自动批准开关（坤哥要求默认通过）
        self.auto_approve = os.environ.get("CLAWKEEPER_AUTO_APPROVE", "false").lower() == "true"

    def approve_all(self):
        """一键放行：设置自动批准模式，后续所有 HIGH 操作自动通过"""
        self.auto_approve = True
        os.environ["CLAWKEEPER_AUTO_APPROVE"] = "true"
        print("[Interceptor] ✅ 已启用自动批准模式，所有操作默认通过")

    def revoke_all(self):
        """撤回自动批准"""
        self.auto_approve = False
        os.environ["CLAWKEEPER_AUTO_APPROVE"] = "false"
        print("[Interceptor] ⏸️ 已关闭自动批准，恢复人工审批")

    # ---------- PR② 核心：intercept() 分层响应 ----------
    def intercept(self, action) -> InterceptAction:
        """
        PR② 核心方法：根据 RiskLevel 决定响应深度

        逻辑：
        1. 查找 RISK_TO_RESPONSE 映射
        2. 根据 InterceptResult 执行对应响应
        3. 返回 InterceptAction（包含是否需要人工审批）
        """
        if not action:
            return InterceptAction(
                result=InterceptResult.LOG_ONLY,
                message="无风险操作，放行"
            )

        risk_level = int(action.level)
        response = self.RISK_TO_RESPONSE.get(risk_level, InterceptResult.LOG_ONLY)

        # 构造响应对象
        ia = InterceptAction(
            result=response,
            message=action.message,
            details=action.details or {},
            pending_approval=(response in (
                InterceptResult.BLOCK_AND_NOTIFY,
                InterceptResult.KILL_AND_ISOLATE
            ))
        )

        # PR② 分支逻辑
        if response == InterceptResult.LOG_ONLY:
            self._do_log_only(action, ia)
        elif response == InterceptResult.WARN_AND_LOG:
            self._do_warn_and_log(action, ia)
        elif response == InterceptResult.BLOCK_AND_NOTIFY:
            self._do_block_and_notify(action, ia)
        elif response == InterceptResult.KILL_AND_ISOLATE:
            self._do_kill_and_isolate(action, ia)

        return ia

    # ---------- LOW/SAFE：仅记录 ----------
    def _do_log_only(self, action, ia: InterceptAction):
        """LOG_ONLY：只写日志，不阻断，不通知"""
        self._write_evidence("LOG_ONLY", action, ia)
        print(f"[Interceptor] 📝 {ia.message}")

    # ---------- MEDIUM：警告+记录 ----------
    def _do_warn_and_log(self, action, ia: InterceptAction):
        """WARN_AND_LOG：飞书告警 + 日志，AI 可继续"""
        self._write_evidence("WARN_AND_LOG", action, ia)
        self.notifier.send(action)  # 发送飞书警告
        print(f"[Interceptor] ⚠️ {ia.message}")

    # ---------- HIGH：拦截+通知 ----------
    def _do_block_and_notify(self, action, ia: InterceptAction):
        """BLOCK_AND_NOTIFY：拦截操作 + 飞书紧急通知 + 等待审批"""
        path = action.details.get("path", "")
        self.blocked_paths.add(path)
        self.pending_actions[path] = {
            "action": action,
            "ia": ia,
            "time": time.time(),
            "approved": False,
        }

        ia.pending_approval = True
        ia.details["blocked"] = True

        # PR⑥：坤哥设置了 auto_approve，自动放行
        if self.auto_approve:
            ia.unblocked = True
            ia.pending_approval = False
            self.pending_actions[path]["approved"] = True
            self.blocked_paths.discard(path)
            print(f"[Interceptor] ✅ [AUTO-APPROVE] 坤哥已设置自动批准，放行: {path}")
            return

        # 正常流程：暂停 + 通知 + 等待审批
        os.environ["CLAWKEEPER_PAUSED"] = "1"
        self.notifier.send(action)
        self._send_approval_request(action)
        print(f"[Interceptor] 🚨 [BLOCK] {ia.message}")
        print(f"[Interceptor] ⏳ 等待坤哥审批: 「允许」放行 / 「拒绝」取消")

    # ---------- CRITICAL：终止+隔离+取证 ----------
    def _do_kill_and_isolate(self, action, ia: InterceptAction):
        """KILL_AND_ISOLATE：终止 + 隔离进程 + 取证 + 飞书紧急告警"""
        path = action.details.get("path", "")
        self.blocked_paths.add(path)
        self.pending_actions[path] = {
            "action": action,
            "ia": ia,
            "time": time.time(),
            "approved": False,
        }


        # PR⑥：坤哥设置了 auto_approve，自动降为 HIGH 级别放行（CRITICAL 仍记录但不隔离）
        if self.auto_approve:
            print(f"[Interceptor] ⚠️ [AUTO-APPROVE] CRITICAL 操作降级放行: {path}")
            self._do_block_and_notify(action, ia)
            return

        # 1. 收集取证数据
        ia.evidence = self._collect_evidence(action)
        ia.pending_approval = True
        ia.details["killed"] = True

        # 2. 设置系统暂停标志
        os.environ["CLAWKEEPER_KILLED"] = "1"
        os.environ["CLAWKEEPER_PAUSED"] = "1"

        # 3. 发送飞书最高级别告警
        self._send_critical_alert(action, ia)

        # 4. 保存取证文件
        self._save_evidence(ia)

        print(f"[Interceptor] 🔴 [KILL] {ia.message}")
        print(f"[Interceptor] 🔒 系统已隔离，等待坤哥紧急审批")

    # ---------- 取证逻辑 ----------
    def _collect_evidence(self, action) -> List[str]:
        """
        收集取证数据（CRITICAL 响应的一部分）
        包括：操作详情、上下文、系统状态快照
        """
        evidence = []
        ts = time.strftime("%Y%m%d_%H%M%S")

        # 1. 操作上下文
        ctx_file = self.evidence_dir / f"context_{ts}.json"
        ctx = {
            "timestamp": ts,
            "action": action.to_dict() if hasattr(action, 'to_dict') else str(action),
            "path": action.details.get("path"),
            "event": action.details.get("event"),
            "level": int(action.level) if hasattr(action, 'level') else 4,
        }
        with open(ctx_file, 'w') as f:
            json.dump(ctx, f, indent=2, ensure_ascii=False)
        evidence.append(str(ctx_file))

        # 2. 进程快照
        try:
            ps_file = self.evidence_dir / f"ps_snapshot_{ts}.txt"
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True, text=True, timeout=5
            )
            with open(ps_file, 'w') as f:
                f.write(result.stdout)
            evidence.append(str(ps_file))
        except Exception:
            pass

        # 3. 最近的文件操作（audit.log 片段）
        try:
            audit_file = self.evidence_dir / f"audit_tail_{ts}.log"
            result = subprocess.run(
                ["tail", "-50", "/root/.openclaw/workspace/clawkeeper/audit.log"],
                capture_output=True, text=True, timeout=5
            )
            with open(audit_file, 'w') as f:
                f.write(result.stdout)
            evidence.append(str(audit_file))
        except Exception:
            pass

        return evidence

    def _save_evidence(self, ia: InterceptAction):
        """保存取证文件索引"""
        idx_file = self.evidence_dir / "evidence_index.json"
        idx = []
        if idx_file.exists():
            with open(idx_file, 'r') as f:
                idx = json.load(f)
        idx.append({
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "message": ia.message,
            "evidence_files": ia.evidence,
        })
        with open(idx_file, 'w') as f:
            json.dump(idx, f, indent=2, ensure_ascii=False)

    # ---------- 飞书通知 ----------
    def _send_approval_request(self, action):
        """发送 HIGH 级审批请求卡片"""
        try:
            card = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {"tag": "plain_text", "content": "🚨 操作拦截 - 需要审批"},
                        "template": "red",
                    },
                    "elements": [
                        {"tag": "markdown", "content": f"**操作**: {action.message}"},
                        {"tag": "markdown", "content": f"**路径**: `{action.details.get('path', '')}`"},
                        {"tag": "markdown", "content": f"**风险**: `HIGH` - 拦截等待人工确认"},
                        {"tag": "hr"},
                        {"tag": "markdown", "content": "**操作**: 回复 `允许` 放行 / `拒绝` 取消"},
                        {"tag": "markdown", "content": "⚠️ 高危操作需要坤哥人工确认后才能执行"},
                    ]
                }
            }
            self._send_card(card)
        except Exception as e:
            print(f"[Interceptor] 审批请求发送失败: {e}")

    def _send_critical_alert(self, action, ia: InterceptAction):
        """发送 CRITICAL 最高级别告警"""
        try:
            card = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {"tag": "plain_text", "content": "🔴🔴🔴 最高风险警报 - 系统已隔离"},
                        "template": "red",
                    },
                    "elements": [
                        {"tag": "markdown", "content": f"**操作**: {action.message}"},
                        {"tag": "markdown", "content": f"**路径**: `{action.details.get('path', '')}`"},
                        {"tag": "markdown", "content": f"**风险**: `CRITICAL` - 系统已终止并隔离"},
                        {"tag": "markdown", "content": f"**取证文件**: {len(ia.evidence)} 个"},
                        {"tag": "hr"},
                        {"tag": "markdown", "content": "🚨 **立即处理**：回复 `允许` 恢复 / `拒绝` 保持隔离"},
                    ]
                }
            }
            self._send_card(card)
        except Exception as e:
            print(f"[Interceptor] 最高警报发送失败: {e}")

    def _send_card(self, card: dict):
        """发送飞书卡片"""
        webhook = os.environ.get(
            "FEISHU_WEBHOOK",
            "https://open.feishu.cn/open-apis/bot/v2/hook/375a8be1-9e3e-4758-a78b-e775fd4d32a1"
        )
        try:
            data = json.dumps(card, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                webhook, data=data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                if result.get("StatusCode") != 0 and result.get("code") != 0:
                    print(f"[Interceptor] 卡片发送失败: {result}")
        except Exception as e:
            print(f"[Interceptor] 卡片发送异常: {e}")

    # ---------- 审批流程 ----------
    def approve(self, path: str) -> bool:
        """
        坤哥批准操作
        解除拦截，恢复 AI 执行
        """
        if path not in self.blocked_paths and path not in self.pending_actions:
            return False

        self.blocked_paths.discard(path)

        if path in self.pending_actions:
            ia = self.pending_actions[path].get("ia")
            ia.pending_approval = False
            ia.unblocked = True
            ia.details["approved_by"] = "kun_ge"
            ia.details["approved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            del self.pending_actions[path]

        os.environ.pop("CLAWKEEPER_KILLED", None)
        os.environ.pop("CLAWKEEPER_PAUSED", None)

        self._send_card({
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": "✅ 坤哥已批准"}, "template": "green"},
                "elements": [{"tag": "markdown", "content": f"**路径**: `{path}`\n**状态**: 已放行"}]
            }
        })
        print(f"[Interceptor] ✅ 坤哥已批准: {path}")
        return True

    def reject(self, path: str) -> bool:
        """
        坤哥拒绝操作
        保持拦截，尝试回退
        """
        if path not in self.blocked_paths and path not in self.pending_actions:
            return False

        self.blocked_paths.discard(path)

        if path in self.pending_actions:
            ia = self.pending_actions[path].get("ia")
            ia.pending_approval = False
            ia.details["rejected_by"] = "kun_ge"
            ia.details["rejected_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            del self.pending_actions[path]

        # 回退操作
        self._rollback_path(path)

        os.environ.pop("CLAWKEEPER_KILLED", None)
        os.environ.pop("CLAWKEEPER_PAUSED", None)

        self._send_card({
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": "❌ 坤哥已拒绝"}, "template": "red"},
                "elements": [{"tag": "markdown", "content": f"**路径**: `{path}`\n**状态**: 已拒绝并回退"}]
            }
        })
        print(f"[Interceptor] ❌ 坤哥已拒绝: {path}")
        return True

    def _rollback_path(self, path: str):
        """尝试回退文件操作（从 Git 恢复）"""
        try:
            workspace = os.environ.get("WORKSPACE", "/root/.openclaw/workspace")
            rel = Path(path).relative_to(workspace)
            result = subprocess.run(
                ["git", "checkout", "--", str(rel)],
                cwd=workspace, capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                print(f"[Interceptor] ✅ 已回退: {path}")
            else:
                print(f"[Interceptor] ⚠️ 回退失败: {result.stderr}")
        except Exception as e:
            print(f"[Interceptor] 回退异常: {e}")

    # ---------- 状态查询 ----------
    def get_pending(self) -> List[dict]:
        """获取待审核操作列表"""
        return [
            {
                "path": path,
                "message": info["ia"].message,
                "level": info["ia"].result.value,
                "pending": info["ia"].pending_approval,
                "waiting_seconds": int(time.time() - info["time"]),
            }
            for path, info in self.pending_actions.items()
        ]

    def is_paused(self) -> bool:
        """检查系统是否暂停"""
        return os.environ.get("CLAWKEEPER_PAUSED") == "1"

    def is_killed(self) -> bool:
        """检查系统是否被 kill"""
        return os.environ.get("CLAWKEEPER_KILLED") == "1"

    def check_and_block_if_paused(self, operation_desc: str = ""):
        """高危操作前检查系统状态"""
        if self.is_paused():
            msg = f"⚠️ 系统已暂停，拒绝执行: {operation_desc}"
            print(f"[Interceptor] {msg}")
            raise SystemExit(f"Operation blocked: system paused - {operation_desc}")

    # ---------- 内部工具 ----------
    def _write_evidence(self, level: str, action, ia: InterceptAction):
        """写响应证据日志"""
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


if __name__ == "__main__":
    from detector import RiskDetector, RiskLevel, Action
    from notifier import FeishuNotifier

    detector = RiskDetector()
    notifier = FeishuNotifier()
    interceptor = Interceptor(detector, notifier)

    # 测试各层级响应
    test_cases = [
        Action(RiskLevel.SAFE, "ALLOW", "SAFE 操作", {"path": "/test"}, True),
        Action(RiskLevel.LOW, "ALLOW", "LOW 操作", {"path": "/test"}, True),
        Action(RiskLevel.MEDIUM, "ALLOW", "MEDIUM 操作", {"path": "/test"}, True),
        Action(RiskLevel.HIGH, "ALLOW", "HIGH 操作", {"path": "/test"}, True),
        Action(RiskLevel.CRITICAL, "ALLOW", "CRITICAL 操作", {"path": "/test"}, True),
    ]

    for action in test_cases:
        print(f"\n测试: {action.message}")
        result = interceptor.intercept(action)
        print(f"  → 响应类型: {result.result.value}")
        print(f"  → 待审批: {result.pending_approval}")
