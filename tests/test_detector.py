#!/usr/bin/env python3
"""
Clawkeeper Detector 测试套件
覆盖：意图分类、正则检测、完整性校验、模式降级
"""

import os
import sys
import json
import tempfile
import hashlib
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from clawkeeper.detector import (
    IntentClassifier,
    RiskDetector,
    RiskLevel,
    Action,
)


class TestIntentClassifier(unittest.TestCase):
    """意图分类器测试"""

    def setUp(self):
        self.ic = IntentClassifier()

    def test_greeting_is_chat(self):
        greetings = ["你好", "您好", "hey", "hi", "hello", "嗨"]
        for g in greetings:
            self.assertEqual(self.ic.detect(g), "chat", f"{g} 应该是 chat")

    def test_thanks_is_chat(self):
        self.assertEqual(self.ic.detect("谢谢"), "chat")
        self.assertEqual(self.ic.detect("thanks"), "chat")

    def test_question_is_chat(self):
        self.assertEqual(self.ic.detect("现在几点了"), "chat")
        self.assertEqual(self.ic.detect("今天几号"), "chat")
        self.assertEqual(self.ic.detect("?"), "chat")

    def test_task_verb_is_work(self):
        work_msgs = [
            "帮我修一下 bug", "帮我审计代码", "请帮我分析",
            "帮我创建", "帮我推送", "帮我执行",
        ]
        for msg in work_msgs:
            self.assertEqual(self.ic.detect(msg), "work", f"{msg} 应该是 work")

    def test_git_command_is_work(self):
        self.assertEqual(self.ic.detect("git push origin main"), "work")
        self.assertEqual(self.ic.detect("git commit -m 'fix'"), "work")

    def test_python_script_is_work(self):
        self.assertEqual(self.ic.detect("python3 scripts/test.py"), "work")
        self.assertEqual(self.ic.detect("bash scripts/deploy.sh"), "work")

    def test_file_path_reference_is_work(self):
        self.assertEqual(self.ic.detect("帮我看 scripts/memory.py"), "work")

    def test_code_block_is_work(self):
        msg = "```python\nprint('hello')\n```"
        self.assertEqual(self.ic.detect(msg), "work")

    def test_multiline_task_is_work(self):
        msg = "帮我完成：\n1. 分析目录\n2. 写代码"
        self.assertEqual(self.ic.detect(msg), "work")

    def test_manual_mode_switch(self):
        self.ic.set_mode("work")
        self.assertEqual(self.ic.detect("随便说"), "work")
        self.ic.set_mode("chat")
        self.assertEqual(self.ic.detect("随便说"), "chat")
        self.ic.set_mode(None)


class TestRiskDetector(unittest.TestCase):
    """风险检测器测试"""

    def setUp(self):
        self.detector = RiskDetector()

    def test_delete_core_file_is_critical(self):
        """删除核心文件 → CRITICAL"""
        for fname in ["AGENTS.md", "SOUL.md", "MEMORY.md"]:
            # 用文件名而非完整路径，filename 匹配
            level = self.detector._get_rule_level(f"/workspace/{fname}", "DELETE")
            self.assertEqual(level, RiskLevel.CRITICAL, f"{fname} DELETE 应为 CRITICAL")

    def test_read_gitcredentials_is_high(self):
        """读取 gitcredentials → HIGH"""
        level = self.detector._get_rule_level("/root/.gitcredentials", "READ")
        self.assertEqual(level, RiskLevel.HIGH)

    def test_cron_events_delete_is_medium(self):
        """cron-events 删除 → MEDIUM（路径含 cron-events/ 即匹配）"""
        level = self.detector._get_rule_level("cron-events/", "DELETE")
        self.assertEqual(level, RiskLevel.MEDIUM)

    def test_public_push_is_medium(self):
        """公共仓 push → MEDIUM"""
        level = self.detector._get_rule_level("/workspace/public/file.txt", "CREATE")
        self.assertEqual(level, RiskLevel.MEDIUM)

    def test_normal_file_is_safe(self):
        """普通文件 → SAFE"""
        level = self.detector._get_rule_level("/workspace/README.md", "MODIFY")
        self.assertEqual(level, RiskLevel.SAFE)

    def test_chat_mode_downgrades_medium(self):
        """日常模式：MEDIUM → LOW"""
        event = {"path": "cron-events/", "event": "DELETE"}
        action = self.detector.evaluate(event, mode="chat")
        self.assertEqual(action.level, RiskLevel.LOW)

    def test_chat_mode_downgrades_high_to_medium(self):
        """日常模式：HIGH → MEDIUM"""
        event = {"path": "/root/.gitcredentials", "event": "READ"}
        action = self.detector.evaluate(event, mode="chat")
        self.assertEqual(action.level, RiskLevel.MEDIUM)

    def test_work_mode_keeps_critical(self):
        """工作模式：保持 CRITICAL"""
        event = {"path": "/workspace/AGENTS.md", "event": "DELETE"}
        action = self.detector.evaluate(event, mode="work")
        self.assertEqual(action.level, RiskLevel.CRITICAL)

    def test_work_mode_keeps_high(self):
        """工作模式：保持 HIGH"""
        event = {"path": "jobs.json", "event": "MODIFY"}
        action = self.detector.evaluate(event, mode="work")
        self.assertEqual(action.level, RiskLevel.HIGH)

    def test_action_contains_mode_tag_work(self):
        """action.message 包含工作模式标识"""
        event = {"path": "/workspace/AGENTS.md", "event": "DELETE"}
        action = self.detector.evaluate(event, mode="work")
        self.assertIn("[工作模式]", action.message)

    def test_action_contains_mode_tag_chat(self):
        """action.message 包含日常模式标识"""
        event = {"path": "/workspace/AGENTS.md", "event": "DELETE"}
        action = self.detector.evaluate(event, mode="chat")
        self.assertIn("[日常模式]", action.message)

    def test_action_can_proceed(self):
        """当前 auto_allow=true，所有 action.can_proceed=True"""
        event = {"path": "/workspace/README.md", "event": "MODIFY"}
        action = self.detector.evaluate(event, mode="work")
        self.assertTrue(action.can_proceed)


class TestIntegrityCheck(unittest.TestCase):
    """PR③ 完整性校验测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_memory = Path(self.temp_dir) / "memory"
        self.temp_memory.mkdir()
        self.original_workspace = None

    def tearDown(self):
        import shutil
        # 恢复原始 workspace
        if self.original_workspace and self.original_workspace != self.temp_dir:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        else:
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_integrity_check_returns_dict(self):
        """memory_integrity_check 返回结构化结果"""
        detector = RiskDetector()
        detector.workspace = self.temp_dir
        test_file = self.temp_memory / "test.md"
        test_file.write_text("# test content")

        results = detector.memory_integrity_check(str(self.temp_memory))

        self.assertIn("test.md", results)
        self.assertIn("checksum", results["test.md"])
        self.assertIn("size", results["test.md"])
        self.assertEqual(len(results["test.md"]["checksum"]), 64)

    def test_checksum_changes_on_content_change(self):
        """内容变化时 checksum 不同"""
        detector = RiskDetector()
        detector.workspace = self.temp_dir
        f1 = self.temp_memory / "a.md"
        f2 = self.temp_memory / "b.md"
        f1.write_text("content A")
        f2.write_text("content B")

        results = detector.memory_integrity_check(str(self.temp_memory))
        self.assertNotEqual(results["a.md"]["checksum"], results["b.md"]["checksum"])

    def test_save_and_verify_integrity(self):
        """直接创建 manifest 文件 → 验证状态为 clean"""
        test_file = self.temp_memory / "persist.md"
        test_file.write_text("persistent content")

        # 手动创建 manifest
        from clawkeeper.auditor import Auditor
        detector = RiskDetector()
        clwk_dir = Path(self.temp_dir) / "clawkeeper"
        clwk_dir.mkdir(exist_ok=True)
        manifest = {
            "version": "1.0",
            "generated_at": "2026-04-19",
            "files": {
                "persist.md": {
                    "checksum": hashlib.sha256(b"persistent content").hexdigest(),
                    "size": 17,
                    "modified": 1234567890.0,
                    "path": str(test_file),
                }
            }
        }
        import json
        with open(clwk_dir / "integrity_manifest.json", "w") as f:
            json.dump(manifest, f)

        auditor = Auditor(workspace=str(self.temp_dir))
        result = auditor._check_file_integrity()
        self.assertEqual(result["status"], "clean")

    def test_verify_detects_tampering(self):
        """验证能检测到篡改"""
        test_file = self.temp_memory / "tamper.md"
        test_file.write_text("original")

        # 手动创建 manifest（原始 checksum）
        from clawkeeper.auditor import Auditor
        import json
        clwk_dir = Path(self.temp_dir) / "clawkeeper"
        clwk_dir.mkdir(exist_ok=True)
        manifest = {
            "version": "1.0",
            "files": {
                "tamper.md": {
                    "checksum": hashlib.sha256(b"original").hexdigest(),
                    "size": 8,
                    "modified": 1234567890.0,
                    "path": str(test_file),
                }
            }
        }
        with open(clwk_dir / "integrity_manifest.json", "w") as f:
            json.dump(manifest, f)

        # 篡改文件内容
        test_file.write_text("modified by attacker")

        auditor = Auditor(workspace=str(self.temp_dir))
        result = auditor._check_file_integrity()
        self.assertEqual(result["status"], "compromised")
        self.assertIn("tamper.md", [c["file"] for c in result["changed"]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
