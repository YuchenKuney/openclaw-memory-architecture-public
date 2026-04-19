#!/usr/bin/env python3
"""
Clawkeeper PR⑥ 用户画像测试套件
"""

import os, sys, json, tempfile, unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from clawkeeper.user_profile import UserProfile, ProfileManager

FAMILIARITY_THRESHOLD = 0.6


class TestUserProfile(unittest.TestCase):
    """用户画像核心测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.profile_file = Path(self.temp_dir) / ".user_profile.json"
        import clawkeeper.user_profile as up
        up.PROFILE_FILE = self.profile_file
        ProfileManager._instance = None
        self.profile = UserProfile()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        ProfileManager._instance = None

    # ===== 熟悉度 =====

    def test_new_profile_familiarity_empty(self):
        """新画像熟悉度为空"""
        self.assertEqual(len(self.profile.data["familiarity"]), 0)

    def test_familiarity_grows_with_use(self):
        """重复使用命令熟悉度增长"""
        for _ in range(5):
            self.profile.record_action("git commit", "EXEC", "/workspace")
        self.assertGreater(
            self.profile.data["familiarity"]["git"],
            0.0
        )

    def test_familiarity_caps_at_one(self):
        """熟悉度上限 1.0"""
        for _ in range(100):
            self.profile.record_action("git push", "EXEC", "/workspace")
        self.assertLessEqual(
            self.profile.data["familiarity"]["git"],
            1.0
        )

    # ===== 动态调整 =====

    def test_new_user_first_git_is_high(self):
        """新用户首次操作 git 保持 HIGH"""
        adj, reason = self.profile.get_adjusted_risk("git push", base_risk=3)
        self.assertEqual(adj, 3)

    def test_familiar_command_gets_downgraded(self):
        """熟悉的命令自动降级"""
        self.profile.data["familiarity"]["git"] = FAMILIARITY_THRESHOLD + 0.1

        adj, reason = self.profile.get_adjusted_risk("git push", base_risk=3)
        self.assertLess(adj, 3, "熟悉的命令应降级")
        self.assertIn("熟悉", reason)

    def test_familiar_docker_gets_downgraded(self):
        """熟悉的 docker 命令降级"""
        self.profile.data["familiarity"]["docker"] = 0.7

        adj, reason = self.profile.get_adjusted_risk("docker build", base_risk=3)
        self.assertLessEqual(adj, 2)

    def test_high_risk_tolerance_lowers_all(self):
        """高风险容忍度整体降级"""
        self.profile.data["risk_tolerance"] = "high"
        self.profile.data["familiarity"]["git"] = FAMILIARITY_THRESHOLD

        adj, reason = self.profile.get_adjusted_risk("git merge", base_risk=3)
        self.assertLessEqual(adj, 2)

    # ===== 画像蒸馏 =====

    def test_distill_no_memory_dir(self):
        """memory/ 不存在时返回 no_memory_dir"""
        result = self.profile.distill_from_memory("/nonexistent")
        self.assertEqual(result["status"], "no_memory_dir")

    def test_distill_finds_git_usage(self):
        """蒸馏能从 memory/ 发现 git 使用"""
        memory_dir = Path(self.temp_dir) / "memory"
        memory_dir.mkdir()
        (memory_dir / "2026-04-19.md").write_text(
            "今天完成了 git push 操作，使用 docker build 构建了镜像"
        )
        result = self.profile.distill_from_memory(str(memory_dir))
        self.assertEqual(result["status"], "ok")
        self.assertGreater(result["events_found"], 0)
        self.assertIn("git", self.profile.data["familiarity"])

    def test_distill_with_danger_signal(self):
        """蒸馏识别危险命令使用"""
        memory_dir = Path(self.temp_dir) / "memory"
        memory_dir.mkdir()
        (memory_dir / "day1.md").write_text(
            "使用 subprocess.run 执行了系统命令"
        )
        result = self.profile.distill_from_memory(str(memory_dir))
        self.assertGreater(result["events_found"], 0)
        self.assertGreater(len(result["learning_notes"]), 0)

    # ===== 画像摘要 =====

    def test_profile_summary_contains_git(self):
        """画像摘要包含 git 信息"""
        self.profile.data["familiarity"]["git"] = 0.75
        summary = self.profile.get_profile_summary()
        self.assertIn("git", summary)
        self.assertIn("75%", summary)

    def test_profile_summary_shows_capabilities(self):
        """画像摘要显示能力"""
        self.profile.data["capabilities"].append("版本控制")
        summary = self.profile.get_profile_summary()
        self.assertIn("版本控制", summary)

    # ===== 能力推断 =====

    def test_infer_git_capabilities(self):
        self.profile.record_action("git clone", "EXEC", "/workspace")
        self.assertIn("协作开发", self.profile.data["capabilities"])

    def test_infer_docker_capabilities(self):
        self.profile.record_action("docker run", "EXEC", "/workspace")
        self.assertIn("容器化", self.profile.data["capabilities"])

    # ===== recent_commands =====

    def test_record_action_updates_recent_commands(self):
        self.profile.record_action("git push", "EXEC", "/workspace")
        self.assertEqual(len(self.profile.data["recent_commands"]), 1)
        self.assertEqual(self.profile.data["recent_commands"][0]["command"], "git push")

    def test_recent_commands_limited_to_50(self):
        for i in range(60):
            self.profile.record_action(f"cmd_{i}", "EXEC", "/workspace")
        self.assertEqual(len(self.profile.data["recent_commands"]), 50)


class TestDistillLogic(unittest.TestCase):
    """蒸馏逻辑详细测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        import clawkeeper.user_profile as up
        up.PROFILE_FILE = Path(self.temp_dir) / ".user_profile.json"
        ProfileManager._instance = None
        self.profile = UserProfile()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        ProfileManager._instance = None

    def test_distill_multiple_tools_increments_events(self):
        """蒸馏多种工具时 events_found 增加"""
        memory_dir = Path(self.temp_dir) / "memory"
        memory_dir.mkdir()
        content = "使用 git clone 和 docker run 和 npm install"
        (memory_dir / "day1.md").write_text(content)
        result = self.profile.distill_from_memory(str(memory_dir))
        self.assertGreater(result["events_found"], 0)
        # git/familiarity 应被更新
        self.assertIn("git", self.profile.data["familiarity"])

    def test_distill_learning_note_records_git(self):
        """蒸馏的学习笔记记录 git 使用"""
        memory_dir = Path(self.temp_dir) / "memory"
        memory_dir.mkdir()
        (memory_dir / "day1.md").write_text("今天做了 git merge 和 git rebase")
        self.profile.distill_from_memory(str(memory_dir))
        self.assertGreater(len(self.profile.data["learning_notes"]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
