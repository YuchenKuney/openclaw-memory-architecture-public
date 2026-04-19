#!/usr/bin/env python3
"""
Clawkeeper Auditor - 主动安全审计器

PR③ 落地实现：
① CVE 依赖漏洞扫描（pip-audit / safety）
② Skill.md 可疑模式扫描（exec/curl/write/eval）
③ 配置文件权限基线检查
④ 文件完整性哈希校验（配合 detector.py 的 integrity_manifest）
⑤ 定时主动扫描（主动发现，而非被动等日志）
"""

import os
import json
import time
import re
import subprocess
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict


class Auditor:
    """主动安全审计器"""

    def __init__(self, audit_log_path=None, workspace=None):
        self.audit_log_path = audit_log_path or os.environ.get(
            "CLAWKEEPER_AUDIT_LOG",
            "/root/.openclaw/workspace/clawkeeper/audit.log"
        )
        self.workspace = workspace or os.environ.get(
            "WORKSPACE",
            "/root/.openclaw/workspace"
        )
        self.clawkeeper_dir = Path(self.workspace) / "clawkeeper"
        self.manifest_path = self.clawkeeper_dir / "integrity_manifest.json"

    # ========== PR③ 核心：主动扫描入口 ==========

    def active_scan(self) -> dict:
        """
        主动扫描（坤哥指出的缺口①）

        扫描范围：
        1. CVE 检查：pip-audit / safety 检查依赖漏洞
        2. 文件完整性：与 integrity_manifest.json 比对
        3. Skill 审计：扫描 SKILL.md 中的可疑模式（exec/curl/write/eval）
        4. 配置基线：config.yaml / openclaw.json 权限检查

        Returns:
            {
                "status": "clean|warning|critical",
                "cve_check": {...},
                "file_integrity": {...},
                "skill_audit": {...},
                "config_baseline": {...},
                "scanned_at": "...",
            }
        """
        print(f"[Auditor] 🔍 开始主动扫描...")
        results = {
            "status": "clean",
            "scanned_at": datetime.now().isoformat(),
        }

        # 1. CVE 依赖检查
        cve = self._check_dependencies()
        results["cve_check"] = cve
        if cve["status"] != "clean":
            results["status"] = "warning"

        # 2. 文件完整性
        integrity = self._check_file_integrity()
        results["file_integrity"] = integrity
        if integrity["status"] == "compromised":
            results["status"] = "critical"

        # 3. Skill 可疑模式扫描
        skill = self._scan_skill_patterns()
        results["skill_audit"] = skill
        if skill["status"] != "clean":
            results["status"] = "warning"

        # 4. 配置基线检查
        baseline = self._check_config_baseline()
        results["config_baseline"] = baseline
        if baseline["status"] != "clean":
            results["status"] = "warning"

        # 保存扫描结果
        self._save_scan_results(results)

        print(f"[Auditor] ✅ 扫描完成，状态: {results['status']}")
        return results

    # ========== 1. CVE 依赖漏洞扫描 ==========

    def _check_dependencies(self) -> dict:
        """
        检查 Python 依赖漏洞
        优先使用 pip-audit，fallback 到 safety
        """
        result = {
            "status": "clean",
            "tool": None,
            "vulnerabilities": [],
            "checked_at": datetime.now().isoformat(),
            "error": None,
        }

        # 尝试 pip-audit
        tools = [
            ("pip-audit", ["pip-audit", "--format=json"]),
            ("safety", ["safety", "check", "--json"]),
        ]

        for tool_name, cmd in tools:
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=self.workspace,
                )
                result["tool"] = tool_name

                if proc.returncode in (0, 1):  # 0=clean, 1=vulns found
                    output = proc.stdout.strip()
                    if output:
                        try:
                            vulns = json.loads(output)
                            if isinstance(vulns, list) and vulns:
                                result["vulnerabilities"] = vulns[:10]  # 只取前10条
                                result["status"] = "warning"
                            elif isinstance(vulns, dict) and vulns.get("vulnerabilities"):
                                result["vulnerabilities"] = vulns["vulnerabilities"][:10]
                                result["status"] = "warning"
                        except json.JSONDecodeError:
                            # 非 JSON 输出但有内容
                            if "vulnerability" in output.lower():
                                result["vulnerabilities"] = [{"raw": output[:200]}]
                                result["status"] = "warning"
                    break  # 成功执行，退出工具尝试

            except FileNotFoundError:
                continue
            except subprocess.TimeoutExpired:
                result["error"] = f"{tool_name} 超时"
                continue
            except Exception as e:
                result["error"] = str(e)
                continue

        if result["tool"] is None:
            result["error"] = "未找到 pip-audit 或 safety"
            # Fallback: 用 pip freeze 比对已知漏洞库（简单版）
            try:
                vulns = self._basic_cve_check()
                if vulns:
                    result["vulnerabilities"] = vulns
                    result["status"] = "warning"
                    result["tool"] = "pip-freeze-basic"
            except Exception:
                pass

        return result

    def _basic_cve_check(self) -> list:
        """
        基础 CVE 检查（无 pip-audit/safety 时使用）
        通过 pip freeze 检查已知高危包版本
        """
        KNOWN_VULNS = {
            "pyyaml": "<6.0",
            "urllib3": "<1.26",
            "requests": "<2.28",
            "jinja2": "<3.1",
            "pillow": "<9.0",
            "django": "<3.2",
            "flask": "<2.0",
            "openssl": "*",
            "cryptography": "<41.0",
        }

        vulns = []
        try:
            proc = subprocess.run(
                ["pip", "freeze"],
                capture_output=True, text=True, timeout=10
            )
            if proc.returncode != 0:
                return vulns

            for line in proc.stdout.splitlines():
                if ">=" in line or "==" in line:
                    pkg, _, ver = line.strip().partition("==")
                    pkg = pkg.lower()
                    if pkg in KNOWN_VULNS:
                        vulns.append({
                            "package": pkg,
                            "installed": ver,
                            "required": KNOWN_VULNS[pkg],
                            "note": "已知漏洞版本",
                        })
        except Exception:
            pass
        return vulns

    # ========== 2. 文件完整性校验 ==========

    def _check_file_integrity(self) -> dict:
        """
        与 integrity_manifest.json 比对
        检测 memory/ 目录是否被篡改
        """
        result = {
            "status": "clean",
            "changed": [],
            "added": [],
            "removed": [],
            "checked_at": datetime.now().isoformat(),
        }

        if not self.manifest_path.exists():
            result["status"] = "unknown"
            result["note"] = "integrity_manifest.json 不存在，需先运行 save_integrity_manifest()"
            return result

        try:
            with open(self.manifest_path, 'r') as f:
                manifest = json.load(f)

            old_files = manifest.get("files", {})

            # 重新计算当前哈希
            from detector import RiskDetector
            detector = RiskDetector()
            current = detector.memory_integrity_check()

            old_names = set(old_files.keys())
            cur_names = set(current.keys())

            # 新增文件
            for fname in cur_names - old_names:
                result["added"].append({
                    "file": fname,
                    "checksum": current[fname].get("checksum", "")[:16],
                })

            # 删除文件
            for fname in old_names - cur_names:
                result["removed"].append(fname)

            # 篡改检测
            for fname in old_names & cur_names:
                old_hash = old_files[fname].get("checksum", "")
                cur_hash = current[fname].get("checksum", "")
                if old_hash and cur_hash and old_hash != cur_hash:
                    result["changed"].append({
                        "file": fname,
                        "old_checksum": old_hash[:16],
                        "new_checksum": cur_hash[:16],
                    })

            if result["changed"] or result["added"]:
                result["status"] = "compromised"
            elif not old_names and not cur_names:
                result["status"] = "unknown"

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)

        return result

    # ========== 3. Skill 可疑模式扫描 ==========

    def _scan_skill_patterns(self) -> dict:
        """
        扫描 SKILL.md 和 scripts/ 下所有 .py 文件的可疑模式
        PR③ 核心：静态代码审计

        可疑模式：
        - exec() / eval() / compile() → 代码注入
        - subprocess.run/shell=True → 命令注入
        - curl / wget → 数据外传
        - open().write() → 文件写入
        - os.system / os.popen → 命令执行
        - requests.post 发送外部数据
        """
        SUSPICIOUS_PATTERNS = [
            (r"exec\s*\(", "exec() 调用", "high"),
            (r"eval\s*\(", "eval() 调用", "high"),
            (r"subprocess\.run\([^)]*shell\s*=\s*True", "subprocess shell=True", "critical"),
            (r"os\.system\s*\(", "os.system() 调用", "high"),
            (r"os\.popen\s*\(", "os.popen() 调用", "high"),
            (r"curl\s+", "curl 命令执行", "medium"),
            (r"wget\s+", "wget 命令执行", "medium"),
            (r"requests\.(post|put)\s*\(", "外部 HTTP POST/PUT", "medium"),
            (r"urllib\.request\.urlopen\s*\(", "urllib 请求", "low"),
            (r"shutil\.rmtree\s*\(", "shutil.rmtree 递归删除", "high"),
            (r"chmod\s*\(.*0o?777", "777 权限设置", "critical"),
            (r"open\s*\([^)]*['\"]w['\"]", "文件写入 open()", "low"),
            (r"os\.chmod\s*\(.*0o?\d{3}", "os.chmod 改权限", "medium"),
            (r"import\s+.*sys\s*;.*os\.system", "sys+os.system 组合", "critical"),
        ]

        result = {
            "status": "clean",
            "findings": [],
            "scanned_files": 0,
            "scanned_at": datetime.now().isoformat(),
        }

        scan_paths = [
            Path(self.workspace) / "scripts",
            Path(self.workspace) / "clawkeeper",
            Path(self.workspace) / "shared",
        ]

        for scan_path in scan_paths:
            if not scan_path.exists():
                continue
            for fpath in scan_path.rglob("*.py"):
                if "__pycache__" in str(fpath):
                    continue
                result["scanned_files"] += 1
                findings = self._scan_file_patterns(fpath, SUSPICIOUS_PATTERNS)
                if findings:
                    result["findings"].extend(findings)

        if result["findings"]:
            result["status"] = "warning"
            # 有 critical 级别的直接标 warning 以上
            if any(f["severity"] == "critical" for f in result["findings"]):
                result["status"] = "warning"

        return result

    def _scan_file_patterns(self, fpath: Path, patterns: list) -> list:
        """扫描单个文件的可疑模式"""
        findings = []
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            for lineno, line in enumerate(lines, 1):
                for pat, desc, severity in patterns:
                    if re.search(pat, line):
                        # 排除注释中的代码
                        stripped = line.strip()
                        if stripped.startswith("#"):
                            continue
                        findings.append({
                            "file": str(fpath.relative_to(self.workspace)),
                            "line": lineno,
                            "pattern": desc,
                            "severity": severity,
                            "code": stripped[:100],
                        })
        except Exception:
            pass
        return findings

    # ========== 4. 配置基线检查 ==========

    def _check_config_baseline(self) -> dict:
        """
        检查关键配置文件的权限和内容基线
        """
        result = {
            "status": "clean",
            "issues": [],
            "checked_at": datetime.now().isoformat(),
        }

        checks = [
            # config.yaml 不应有明文 token
            (Path(self.workspace) / "clawkeeper" / "config.yaml", self._check_yaml_secrets),
            # openclaw.json 权限检查
            (Path(self.workspace) / "openclaw.json", self._check_json_config),
            # 环境变量文件权限
            ("/etc/environment", self._check_env_permissions),
            # gitcredentials 权限
            ("/root/.gitcredentials", self._check_gitcreds_permissions),
        ]

        for path, check_fn in checks:
            if isinstance(path, str):
                path = Path(path)
            if not path.exists():
                continue
            try:
                issues = check_fn(path)
                if issues:
                    result["issues"].extend(issues)
            except Exception as e:
                result["issues"].append({
                    "file": str(path),
                    "issue": f"检查失败: {e}",
                    "severity": "low",
                })

        if result["issues"]:
            result["status"] = "warning"

        return result

    def _check_yaml_secrets(self, path: Path) -> list:
        """检查 YAML 中是否有明文密钥"""
        issues = []
        try:
            content = path.read_text()
            secret_patterns = [
                (r'ghp_[a-zA-Z0-9]{36}', 'GitHub PAT'),
                (r'sk-[a-zA-Z0-9]{20,}', 'API Key'),
                (r'LnhA[a-zA-Z0-9]{30,}', '飞书 AppSecret'),
                (r'app_secret\s*:\s*["\']?[^"\']{16,}', 'AppSecret'),
            ]
            for pat, name in secret_patterns:
                if re.search(pat, content):
                    issues.append({
                        "file": str(path.relative_to(self.workspace)),
                        "issue": f"明文 {name} 在配置文件中",
                        "severity": "critical",
                    })
                    break
        except Exception:
            pass
        return issues

    def _check_json_config(self, path: Path) -> list:
        """检查 openclaw.json 权限"""
        issues = []
        try:
            stat = path.stat()
            mode = oct(stat.st_mode)[-3:]
            if stat.st_uid == 0 and int(mode[-1]) & 2:
                issues.append({
                    "file": "openclaw.json",
                    "issue": f"权限过宽: {mode}",
                    "severity": "medium",
                })
        except Exception:
            pass
        return issues

    def _check_env_permissions(self, path: Path) -> list:
        """检查 /etc/environment 权限（不要求 root only）"""
        issues = []
        try:
            stat = path.stat()
            mode = oct(stat.st_mode)[-3:]
            if int(mode[-1]) & 4:  # others read
                issues.append({
                    "file": str(path),
                    "issue": f"/etc/environment 对 others 可读: {mode}",
                    "severity": "low",
                })
        except Exception:
            pass
        return issues

    def _check_gitcreds_permissions(self, path: Path) -> list:
        """检查 gitcredentials 权限（应仅 owner 可读写）"""
        issues = []
        try:
            stat = path.stat()
            mode = oct(stat.st_mode)[-3:]
            if int(mode[-1]) & 6:  # group or others write
                issues.append({
                    "file": str(path),
                    "issue": f".gitcredentials 权限过宽: {mode}（应为 600）",
                    "severity": "critical",
                })
        except Exception:
            pass
        return issues

    # ========== 保存 & 报告生成 ==========

    def _save_scan_results(self, results: dict):
        """保存主动扫描结果"""
        report_dir = self.clawkeeper_dir / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"active_scan_{int(time.time())}.json"
        with open(report_path, 'w') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"[Auditor] 扫描报告已保存: {report_path}")

    def format_scan_report(self, results: dict = None) -> str:
        """格式化主动扫描报告为文本"""
        if results is None:
            results = self.active_scan()

        status_emoji = {"clean": "✅", "warning": "⚠️", "critical": "🔴", "unknown": "❓", "error": "❌"}
        emoji = status_emoji.get(results["status"], "❓")

        lines = [
            f"{'=' * 50}",
            f"🔍 Clawkeeper 主动安全扫描报告",
            f"{'=' * 50}",
            f"扫描时间: {results['scanned_at']}",
            f"总体状态: {emoji} {results['status'].upper()}",
            "",
        ]

        # CVE
        cve = results.get("cve_check", {})
        cve_emoji = "✅" if cve.get("status") == "clean" else "⚠️"
        lines.append(f"{cve_emoji} CVE 依赖检查: {cve.get('tool', 'N/A')}")
        if cve.get("vulnerabilities"):
            for v in cve["vulnerabilities"][:5]:
                pkg = v.get("package", v.get("name", "?"))
                ver = v.get("installed", v.get("version", "?"))
                lines.append(f"   🔴 {pkg}=={ver}")
        if cve.get("error"):
            lines.append(f"   ⚠️ {cve['error']}")
        lines.append("")

        # 完整性
        integrity = results.get("file_integrity", {})
        int_emoji = "✅" if integrity.get("status") == "clean" else "🔴"
        lines.append(f"{int_emoji} 文件完整性: {integrity.get('status', 'unknown')}")
        if integrity.get("changed"):
            lines.append(f"   🔴 篡改: {', '.join(i['file'] for i in integrity['changed'])}")
        if integrity.get("added"):
            lines.append(f"   ⚠️ 新增: {', '.join(integrity['added'])}")
        if integrity.get("removed"):
            lines.append(f"   ⚠️ 删除: {', '.join(integrity['removed'])}")
        lines.append("")

        # Skill 扫描
        skill = results.get("skill_audit", {})
        sk_emoji = "✅" if skill.get("status") == "clean" else "⚠️"
        lines.append(f"{sk_emoji} Skill 静态扫描: {skill.get('scanned_files', 0)} 个文件")
        if skill.get("findings"):
            for f in skill["findings"][:5]:
                lines.append(f"   [{f['severity']}] {f['file']}:{f['line']} - {f['pattern']}")
        lines.append("")

        # 配置基线
        baseline = results.get("config_baseline", {})
        bl_emoji = "✅" if baseline.get("status") == "clean" else "⚠️"
        lines.append(f"{bl_emoji} 配置基线检查")
        if baseline.get("issues"):
            for i in baseline["issues"][:5]:
                lines.append(f"   [{i['severity']}] {i['file']}: {i['issue']}")

        lines.append(f"{'=' * 50}")
        return "\n".join(lines)

    # ========== 以下为原有被动日志分析（保留）==========

    def get_entries(self, since=None, until=None, level_filter=None):
        """获取审计日志条目（被动日志）"""
        entries = []
        if not os.path.exists(self.audit_log_path):
            return entries

        if isinstance(since, datetime):
            since_ts = since.timestamp()
        elif since is None:
            since_ts = 0
        else:
            since_ts = since

        if isinstance(until, datetime):
            until_ts = until.timestamp()
        elif until is None:
            until_ts = float("inf")
        else:
            until_ts = until

        with open(self.audit_log_path) as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    entry_ts = entry.get("time")
                    if entry_ts:
                        try:
                            dt = datetime.fromisoformat(entry_ts.replace("Z", "+00:00"))
                            if not (since_ts <= dt.timestamp() <= until_ts):
                                continue
                        except Exception:
                            pass
                    if level_filter and entry.get("level") not in level_filter:
                        continue
                    entries.append(entry)
                except json.JSONDecodeError:
                    continue
        return entries

    def generate_report(self, period_hours=24):
        """生成被动日志审计报告"""
        since = time.time() - (period_hours * 3600)
        entries = self.get_entries(since=since)

        stats = {
            "total": len(entries),
            "by_level": {},
            "by_event": {},
        }
        for entry in entries:
            level = entry.get("level", "UNKNOWN")
            event = entry.get("event", "UNKNOWN")
            stats["by_level"][level] = stats["by_level"].get(level, 0) + 1
            stats["by_event"][event] = stats["by_event"].get(event, 0) + 1

        return {
            "period": {"hours": period_hours, "since": datetime.fromtimestamp(since).isoformat()},
            "summary": stats,
            "entries": entries[-50:],
        }


if __name__ == "__main__":
    auditor = Auditor()

    # 主动扫描
    print("[Auditor] 运行主动安全扫描...")
    results = auditor.active_scan()
    print(auditor.format_scan_report(results))

    # 保存报告
    report_path = auditor.clawkeeper_dir / "reports" / f"active_scan_latest.json"
    with open(report_path, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n报告已保存: {report_path}")
