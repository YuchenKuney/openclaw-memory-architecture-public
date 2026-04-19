#!/usr/bin/env python3
"""
Clawkeeper Interceptor 测试套件
覆盖：四级分层响应（LOG_ONLY / WARN_AND_LOG / BLOCK_AND_NOTIFY / KILL_AND_ISOLATE）
"""

import os
import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from clawkeeper.detector import RiskLevel, Action
from clawkeeper.interceptor import (
    Interceptor,
    InterceptResult,
    InterceptAction,
)


class MockNotifier:
    def __init__(self):
        self.sent_messages = []
        self.sent_cards = []

    def send(self, action):
        msg = action.message if hasattr(action, 'message') else str(action)
        self.sent_messages.append(msg)

    def send_simple(self, msg, level="INFO"):
        self.sent_messages.append(f"[{level}] {msg}")


class MockDetector:
    pass


class TestInterceptResult(unittest.TestCase):
    """分层响应类型测试"""

    def test_risk_mapping(self):
        interceptor = Interceptor(MockDetector(), MockNotifier())
        self.assertEqual(interceptor.RISK_TO_RESPONSE[0], InterceptResult.LOG_ONLY)
        self.assertEqual(interceptor.RISK_TO_RESPONSE[1], InterceptResult.LOG_ONLY)
        self.assertEqual(interceptor.RISK_TO_RESPONSE[2], InterceptResult.WARN_AND_LOG)
        self.assertEqual(interceptor.RISK_TO_RESPONSE[3], InterceptResult.BLOCK_AND_NOTIFY)
        self.assertEqual(interceptor.RISK_TO_RESPONSE[4], InterceptResult.KILL_AND_ISOLATE)


class TestLayeredResponses(unittest.TestCase):
    """四级分层响应测试"""

    def setUp(self):
        self.detector = MockDetector()
        self.notifier = MockNotifier()
        self.interceptor = Interceptor(self.detector, self.notifier)
        os.environ.pop("CLAWKEEPER_PAUSED", None)
        os.environ.pop("CLAWKEEPER_KILLED", None)

    def tearDown(self):
        os.environ.pop("CLAWKEEPER_PAUSED", None)
        os.environ.pop("CLAWKEEPER_KILLED", None)

    def _make_action(self, level_value, path="/test/path"):
        """创建真实的 Action 对象，而非 MagicMock"""
        action = Action(
            level=RiskLevel(level_value),
            action_type="ALLOW",
            message=f"[{RiskLevel(level_value).name}] Test",
            details={"path": path},
            can_proceed=True,
        )
        return action

    # ===== SAFE (0) → LOG_ONLY =====

    def test_safe_is_log_only(self):
        """SAFE → LOG_ONLY，不通知，不拦截"""
        action = self._make_action(0)
        result = self.interceptor.intercept(action)
        self.assertEqual(result.result, InterceptResult.LOG_ONLY)
        self.assertFalse(result.pending_approval)
        self.assertEqual(len(self.notifier.sent_messages), 0)

    # ===== LOW (1) → LOG_ONLY =====

    def test_low_is_log_only(self):
        """LOW → LOG_ONLY，不通知，不拦截"""
        action = self._make_action(1)
        result = self.interceptor.intercept(action)
        self.assertEqual(result.result, InterceptResult.LOG_ONLY)

    # ===== MEDIUM (2) → WARN_AND_LOG =====

    def test_medium_is_warn_and_log(self):
        """MEDIUM → WARN_AND_LOG，发送飞书警告"""
        action = self._make_action(2)
        result = self.interceptor.intercept(action)
        self.assertEqual(result.result, InterceptResult.WARN_AND_LOG)
        self.assertFalse(result.pending_approval)
        self.assertGreater(len(self.notifier.sent_messages), 0)

    # ===== HIGH (3) → BLOCK_AND_NOTIFY =====

    def test_high_is_block_and_notify(self):
        """HIGH → BLOCK_AND_NOTIFY，拦截并等待审批"""
        action = self._make_action(3, "/workspace/secret.md")
        result = self.interceptor.intercept(action)

        self.assertEqual(result.result, InterceptResult.BLOCK_AND_NOTIFY)
        self.assertTrue(result.pending_approval)
        self.assertIn("/workspace/secret.md", self.interceptor.blocked_paths)

    def test_high_block_tracks_pending_action(self):
        """HIGH 拦截后 pending_actions 包含该操作"""
        action = self._make_action(3, "/workspace/sensitive.json")
        self.interceptor.intercept(action)

        pending = self.interceptor.get_pending()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["path"], "/workspace/sensitive.json")

    # ===== CRITICAL (4) → KILL_AND_ISOLATE =====

    def test_critical_is_kill_and_isolate(self):
        """CRITICAL → KILL_AND_ISOLATE，系统隔离"""
        action = self._make_action(4, "/workspace/AGENTS.md")
        result = self.interceptor.intercept(action)

        self.assertEqual(result.result, InterceptResult.KILL_AND_ISOLATE)
        self.assertTrue(result.pending_approval)
        self.assertEqual(os.environ.get("CLAWKEEPER_KILLED"), "1")
        self.assertEqual(os.environ.get("CLAWKEEPER_PAUSED"), "1")

    def test_critical_collects_evidence(self):
        """CRITICAL 响应收集取证数据"""
        action = self._make_action(4, "/workspace/core.md")
        result = self.interceptor.intercept(action)

        self.assertIsNotNone(result.evidence)
        self.assertIsInstance(result.evidence, list)


class TestApprovalFlow(unittest.TestCase):
    """审批流程测试"""

    def setUp(self):
        self.detector = MockDetector()
        self.notifier = MockNotifier()
        self.interceptor = Interceptor(self.detector, self.notifier)
        os.environ.pop("CLAWKEEPER_PAUSED", None)
        os.environ.pop("CLAWKEEPER_KILLED", None)

    def _make_action(self, level_value, path="/test/path"):
        return Action(
            level=RiskLevel(level_value),
            action_type="ALLOW",
            message=f"[{RiskLevel(level_value).name}] Test",
            details={"path": path},
            can_proceed=True,
        )

    def tearDown(self):
        os.environ.pop("CLAWKEEPER_PAUSED", None)
        os.environ.pop("CLAWKEEPER_KILLED", None)

    def test_approve_unblocks_and_resumes(self):
        """批准后解除拦截，恢复系统"""
        action = self._make_action(3, "/workspace/test.txt")
        self.interceptor.intercept(action)

        self.assertTrue(self.interceptor.is_paused())
        self.assertIn("/workspace/test.txt", self.interceptor.blocked_paths)

        ok = self.interceptor.approve("/workspace/test.txt")
        self.assertTrue(ok)
        self.assertNotIn("/workspace/test.txt", self.interceptor.blocked_paths)
        self.assertFalse(self.interceptor.is_paused())

    def test_reject_unblocks_and_rolls_back(self):
        """拒绝后解除拦截，尝试回退"""
        action = self._make_action(3, "/tmp/reject.txt")
        self.interceptor.intercept(action)

        ok = self.interceptor.reject("/tmp/reject.txt")
        self.assertTrue(ok)
        self.assertNotIn("/tmp/reject.txt", self.interceptor.blocked_paths)
        self.assertFalse(self.interceptor.is_paused())

    def test_approve_nonexistent_returns_false(self):
        ok = self.interceptor.approve("/nonexistent/path")
        self.assertFalse(ok)

    def test_reject_nonexistent_returns_false(self):
        ok = self.interceptor.reject("/nonexistent/path")
        self.assertFalse(ok)


class TestCheckAndBlock(unittest.TestCase):
    """check_and_block_if_paused 测试"""

    def setUp(self):
        self.detector = MockDetector()
        self.notifier = MockNotifier()
        self.interceptor = Interceptor(self.detector, self.notifier)

    def test_normal_passes(self):
        try:
            self.interceptor.check_and_block_if_paused("normal operation")
        except SystemExit:
            self.fail("正常状态不应退出")

    def test_paused_raises_exit(self):
        os.environ["CLAWKEEPER_PAUSED"] = "1"
        with self.assertRaises(SystemExit) as ctx:
            self.interceptor.check_and_block_if_paused("dangerous operation")
        self.assertIn("system paused", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
