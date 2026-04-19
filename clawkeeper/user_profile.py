#!/usr/bin/env python3
"""
Clawkeeper User Profile - 用户画像引擎

PR⑥ 核心：动态风险调整
- 记录用户行为轨迹（每条操作）
- 从 memory/ 日记日志中蒸馏提纯用户能力
- 生成用户画像，调整风险等级

三层记忆联动：
  memory/ 日记 → 日志蒸馏 → 用户画像 → detector 风险调整

用户画像内容：
  - familiarity: 各技术/命令的熟悉程度（0.0 - 1.0）
  - behavior_patterns: 行为模式
  - risk_tolerance: 风险容忍度（随时间动态调整）
  - last_updated: 最后更新时间
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, List, Set, Optional
from collections import defaultdict, Counter
from datetime import datetime

WORKSPACE = Path("/root/.openclaw/workspace")
PROFILE_FILE = Path("/root/.openclaw/workspace/.user_profile.json")


class UserProfile:
    """用户画像"""

    # 命令/技术 → 初始风险等级
    COMMAND_INITIAL_RISK = {
        "git": {"level": "HIGH", "reason": "仓库操作"},
        "npm": {"level": "HIGH", "reason": "包管理"},
        "pip": {"level": "HIGH", "reason": "包安装"},
        "docker": {"level": "HIGH", "reason": "容器操作"},
        "curl": {"level": "MEDIUM", "reason": "网络请求"},
        "chmod": {"level": "MEDIUM", "reason": "权限修改"},
        "ssh": {"level": "MEDIUM", "reason": "远程连接"},
        "subprocess": {"level": "MEDIUM", "reason": "子进程执行"},
        "exec": {"level": "HIGH", "reason": "代码执行"},
        "eval": {"level": "HIGH", "reason": "动态代码"},
        "rm": {"level": "LOW", "reason": "文件删除"},
        "kill": {"level": "HIGH", "reason": "进程终止"},
    }

    # 熟悉度阈值：达到此阈值后自动降级风险
    FAMILIARITY_THRESHOLD = 0.6

    def __init__(self):
        self.data = {
            "version": "1.0",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_distilled": None,
            "familiarity": {},    # 命令熟悉度 0.0-1.0
            "behavior_patterns": [],
            "risk_tolerance": "normal",  # low / normal / high
            "total_events": 0,
            "recent_commands": [],  # 最近 N 条命令
            "capabilities": [],     # 能力列表（从行为中推断）
            "learning_notes": [],   # 从日志中学习的笔记
        }
        self.load()

    # ============ 持久化 ============

    def load(self):
        if PROFILE_FILE.exists():
            try:
                with open(PROFILE_FILE, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
            except Exception:
                pass

    def save(self):
        self.data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(PROFILE_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    # ============ 行为记录 ============

    def record_action(self, command: str, event_type: str, path: str = ""):
        """
        记录用户操作
        每条操作都被记录，用于后续画像学习
        """
        self.data["total_events"] += 1

        # 提取命令关键词
        cmd_lower = command.lower()
        tokens = cmd_lower.split()

        # 更新最近命令（保留最后50条）
        self.data["recent_commands"].append({
            "command": command,
            "event": event_type,
            "path": path,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        if len(self.data["recent_commands"]) > 50:
            self.data["recent_commands"] = self.data["recent_commands"][-50:]

        # 更新熟悉度
        for token in tokens:
            if token in self.COMMAND_INITIAL_RISK:
                self._update_familiarity(token, delta=0.15)

        # 推断能力（从行为模式中学习）
        self._infer_capabilities(command)

    def _update_familiarity(self, command: str, delta: float):
        """增加命令熟悉度"""
        if command not in self.data["familiarity"]:
            self.data["familiarity"][command] = 0.0

        # 熟悉度增长（衰减：越熟悉增长越慢）
        current = self.data["familiarity"][command]
        self.data["familiarity"][command] = min(1.0, current + delta * (1 - current))

    def _infer_capabilities(self, command: str):
        """从命令推断用户能力"""
        capability_map = {
            "git": ["版本控制", "协作开发"],
            "docker": ["容器化", "DevOps"],
            "npm": ["前端开发", "包管理"],
            "pip": ["Python开发"],
            "ssh": ["远程运维"],
            "python": ["编程开发"],
            "bash": ["Shell脚本", "系统运维"],
            "curl": ["API测试", "网络调试"],
        }

        cmd_lower = command.lower()
        for cmd, caps in capability_map.items():
            if cmd in cmd_lower:
                for cap in caps:
                    if cap not in self.data["capabilities"]:
                        self.data["capabilities"].append(cap)

    # ============ 画像蒸馏（核心）============

    def distill_from_memory(self, memory_dir: str = None) -> Dict:
        """
        从 memory/ 日记日志中蒸馏提纯用户画像
        三层记忆联动：memory/ 日记 → 画像更新

        分析 memory/YYYY-MM-DD.md 中的操作记录，
        识别用户行为模式变化，动态调整风险等级
        """
        memory_dir = memory_dir or str(WORKSPACE / "memory")
        mem_path = Path(memory_dir)
        if not mem_path.exists():
            return {"status": "no_memory_dir", "events_found": 0}

        events_found = 0
        learning_notes = []

        for md_file in sorted(mem_path.glob("*.md")):
            try:
                content = md_file.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue

            # 识别 git 使用模式
            if "git" in content.lower():
                events_found += content.lower().count("git")
                self._update_familiarity("git", delta=0.3)
                learning_notes.append(f"{md_file.name}: 发现 git 使用")

            # 识别 docker 使用
            if "docker" in content.lower():
                events_found += 1
                self._update_familiarity("docker", delta=0.3)
                learning_notes.append(f"{md_file.name}: 发现 docker 使用")

            # 识别危险命令（但用户成功执行 → 说明熟悉）
            danger_signals = ["subprocess.run", "shell=True", "eval(", "exec("]
            for signal in danger_signals:
                if signal in content:
                    events_found += 1
                    # 成功使用危险命令说明用户知道风险，降级警告
                    learning_notes.append(
                        f"{md_file.name}: 用户使用了 {signal}（已熟悉，降级风险）"
                    )

            # 识别仓库操作
            repo_signals = ["push", "commit", "branch", "merge", "PR"]
            for sig in repo_signals:
                if sig.lower() in content.lower():
                    events_found += 1
                    self._update_familiarity("git", delta=0.2)

        # 如果发现用户开始使用新工具，更新风险容忍度
        if learning_notes:
            active_tools = [cmd for cmd, fam in self.data["familiarity"].items()
                           if fam >= self.FAMILIARITY_THRESHOLD]
            if len(active_tools) > 3:
                self.data["risk_tolerance"] = "high"
                learning_notes.append("用户熟悉多种工具，提高风险容忍度")

        self.data["learning_notes"] = learning_notes[-10:]  # 保留最近10条
        self.data["last_distilled"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save()

        return {
            "status": "ok",
            "events_found": events_found,
            "learning_notes": learning_notes,
            "active_tools": len([f for f in self.data["familiarity"].values() if f >= self.FAMILIARITY_THRESHOLD]),
        }

    # ============ 风险查询（给 detector 用）============

    def get_adjusted_risk(self, command: str, base_risk: int) -> tuple:
        """
        根据用户画像动态调整风险等级
        返回: (adjusted_risk, reason)

        逻辑：
        - 新用户/不熟悉的命令 → 严格（保持 base_risk 或升级）
        - 熟悉度 > 阈值 → 降级（HIGH→MEDIUM，MEDIUM→LOW）
        - 风险容忍度高 → 放宽
        """
        cmd_lower = command.lower()
        tokens = cmd_lower.split()

        # 1. 检查命令熟悉度
        for token in tokens:
            if token in self.data["familiarity"]:
                fam = self.data["familiarity"][token]
                if fam >= self.FAMILIARITY_THRESHOLD:
                    # 熟悉该命令，降级处理
                    if base_risk >= 3:  # HIGH/CRITICAL
                        adjusted = max(base_risk - 1, 2)  # 降一级，最低 MEDIUM
                        return adjusted, f"用户已熟悉 [{token}]（熟悉度{fam:.0%}），自动降级"
                    elif base_risk == 2:  # MEDIUM
                        if self.data["risk_tolerance"] == "high":
                            return 1, f"用户风险容忍度高，[{token}] 降为 LOW"
                        return base_risk, f"[{token}] 保持 MEDIUM（熟悉度{fam:.0%}）"

        # 2. 风险容忍度高时整体降级
        if self.data["risk_tolerance"] == "high" and base_risk >= 2:
            return base_risk - 1, f"风险容忍度高，降为 {base_risk - 1}"

        # 3. 新用户：第一次遇到某类命令，升级
        unknown_commands = [
            "git", "npm", "pip", "docker", "curl",
            "subprocess", "ssh", "chmod"
        ]
        for token in tokens:
            if token in unknown_commands:
                if token not in self.data["familiarity"]:
                    # 新用户第一次操作该命令
                    if base_risk == 1:  # LOW → MEDIUM（新增观测）
                        return 2, f"新用户首次操作 [{token}]，提高观测级别"

        return base_risk, "保持原级别"

    def is_command_familiar(self, command: str) -> bool:
        """判断用户是否熟悉某命令"""
        cmd_lower = command.lower()
        for cmd, fam in self.data["familiarity"].items():
            if cmd in cmd_lower and fam >= self.FAMILIARITY_THRESHOLD:
                return True
        return False

    def get_profile_summary(self) -> str:
        """获取画像摘要（人类可读）"""
        lines = [
            f"用户画像 v{self.data['version']}",
            f"创建时间: {self.data['created_at']}",
            f"总事件数: {self.data['total_events']}",
            f"风险容忍度: {self.data['risk_tolerance']}",
            "",
            "命令熟悉度:",
        ]

        for cmd, fam in sorted(self.data["familiarity"].items(), key=lambda x: x[1], reverse=True):
            bar = "█" * int(fam * 10) + "░" * (10 - int(fam * 10))
            status = "🟢 熟悉" if fam >= self.FAMILIARITY_THRESHOLD else "🔵 学习"
            lines.append(f"  {cmd:12s} [{bar}] {fam:.0%} {status}")

        if self.data["capabilities"]:
            lines.append("")
            lines.append(f"能力: {', '.join(self.data['capabilities'][:5])}")

        if self.data["learning_notes"]:
            lines.append("")
            lines.append("最近学习:")
            for note in self.data["learning_notes"][-3:]:
                lines.append(f"  • {note}")

        return "\n".join(lines)

    def print_profile(self):
        print(self.get_profile_summary())


class ProfileManager:
    """画像管理器（全局单例）"""

    _instance: Optional[UserProfile] = None

    @classmethod
    def get_profile(cls) -> UserProfile:
        if cls._instance is None:
            cls._instance = UserProfile()
        return cls._instance

    @classmethod
    def reset(cls):
        """重置画像（用于测试）"""
        cls._instance = None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Clawkeeper 用户画像引擎")
    parser.add_argument('--show', '-s', action='store_true', help='显示用户画像')
    parser.add_argument('--distill', '-d', action='store_true', help='从 memory/ 蒸馏画像')
    parser.add_argument('--record', '-r', nargs=3, metavar=('CMD', 'EVENT', 'PATH'),
                        help='记录操作: --record "git push" READ /workspace')
    parser.add_argument('--check', '-c', metavar='COMMAND', help='检查命令熟悉度')
    args = parser.parse_args()

    profile = ProfileManager.get_profile()

    if args.show or (not args.distill and not args.record and not args.check):
        profile.print_profile()

    elif args.distill:
        result = profile.distill_from_memory()
        print(f"蒸馏结果: {result}")
        print()
        profile.print_profile()

    elif args.record:
        cmd, event, path = args.record
        profile.record_action(cmd, event, path)
        profile.save()
        print(f"✅ 记录: {cmd} ({event})")

    elif args.check:
        base_risk = 3  # 默认 HIGH
        adj, reason = profile.get_adjusted_risk(args.check, base_risk)
        familiar = profile.is_command_familiar(args.check)
        print(f"命令: {args.check}")
        print(f"熟悉度: {'🟢 已熟悉' if familiar else '🔵 不熟悉'}")
        print(f"原始风险: {base_risk} → 调整后: {adj}")
        print(f"原因: {reason}")


if __name__ == "__main__":
    main()
