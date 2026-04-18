#!/usr/bin/env python3
"""
Memory Watchdog - 记忆看门狗 (标准自动运维系统)

架构：
├─ Scheduler (cron)          # 定时触发
├─ Decision Engine (判断)     # 决策是否执行
├─ Executor (执行)            # 实际执行
├─ Lock (防冲突)              # 文件锁
└─ Decision Log (记录原因)    # 记录决策过程

功能：
1. 定时检查记忆状态
2. 自动决策是否需要清理/提炼
3. 执行必要的维护操作
4. 记录所有决策的原因
5. 参数化配置，支持不同环境

配置（.watchdog.json）:
{
  "archive_threshold": 10,    # 待归档文件超过此值时清理
  "distill_days": 7,          # 每N天提炼一次
  "check_interval_hours": 6,  # 检查间隔
  "auto_cleanup_enabled": true,
  "decisions_log": []         # 决策日志
}

使用：
python3 memory_watchdog.py --run --confirm   # 生产环境
python3 memory_watchdog.py --dry-run        # 测试模式
"""

import os
import sys
import json
import fcntl
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# 导入相关模块
sys.path.insert(0, str(Path(__file__).parent))
from memory_lifecycle import LifecycleManager
from knowledge_graph import KnowledgeGraph
from rule_manager import RuleManager
from log_distiller import LogDistiller

CONFIG_FILE = Path("/root/.openclaw/workspace/.watchdog.json")
LOCK_FILE = Path("/tmp/memory_watchdog.lock")
DECISION_LOG_FILE = Path("/root/.openclaw/workspace/memory/watchdog_decisions.json")

class WatchdogConfig:
    """看门狗配置（参数化）"""
    
    DEFAULT = {
        "archive_threshold": 10,       # 待归档文件超过此值时清理
        "distill_days": 7,            # 每N天提炼一次
        "check_interval_hours": 6,    # 检查间隔（小时）
        "auto_cleanup_enabled": True,
        "decisions_log_max": 100,     # 最多保留N条决策日志
    }
    
    def __init__(self):
        self.config = self.load()
    
    def load(self) -> dict:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                return {**self.DEFAULT, **json.load(f)}
        return self.DEFAULT.copy()
    
    def save(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get(self, key, default=None):
        return self.config.get(key, default)
    
    def set(self, key, value):
        self.config[key] = value
        self.save()
    
    def update(self, updates: dict):
        self.config.update(updates)
        self.save()

class Decision:
    """决策记录"""
    
    def __init__(self, action: str, reason: str, result: str = None, details: dict = None):
        self.timestamp = datetime.now().isoformat()
        self.action = action
        self.reason = reason
        self.result = result  # success | cancelled | failed
        self.details = details or {}
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "action": self.action,
            "reason": self.reason,
            "result": self.result,
            "details": self.details
        }

class DecisionLogger:
    """决策日志"""
    
    def __init__(self, max_logs: int = 100):
        self.max_logs = max_logs
        self.decisions: List[Decision] = []
        self.load()
    
    def load(self):
        if DECISION_LOG_FILE.exists():
            with open(DECISION_LOG_FILE, 'r') as f:
                data = json.load(f)
                for d in data.get("decisions", []):
                    self.decisions.append(Decision(
                        d["action"], d["reason"], d.get("result"), d.get("details")
                    ))
    
    def save(self):
        # 只保留最近的N条
        recent = self.decisions[-self.max_logs:]
        data = {
            "decisions": [d.to_dict() for d in recent]
        }
        with open(DECISION_LOG_FILE, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def add(self, decision: Decision):
        self.decisions.append(decision)
        self.save()
    
    def get_recent(self, n: int = 10) -> List[Decision]:
        return self.decisions[-n:]
    
    def print_log(self, n: int = 10):
        print("=" * 80)
        print("📋 Decision Log - 决策日志")
        print("=" * 80)
        recent = self.get_recent(n)
        if not recent:
            print("（暂无决策记录）")
        for d in reversed(recent):
            status_icon = {
                "success": "✅",
                "cancelled": "⏭️",
                "failed": "❌",
                "pending": "⏳"
            }.get(d.result, "•")
            print(f"\n{status_icon} [{d.timestamp}]")
            print(f"   动作: {d.action}")
            print(f"   原因: {d.reason}")
            if d.result:
                print(f"   结果: {d.result}")
        print("\n" + "=" * 80)

class MemoryWatchdog:
    """记忆看门狗 - 标准自动运维系统"""
    
    def __init__(self, dry_run: bool = False, confirm: bool = False):
        self.config = WatchdogConfig()
        self.lifecycle = LifecycleManager()
        self.kg = KnowledgeGraph()
        self.rm = RuleManager()
        self.distiller = LogDistiller()
        self.decision_logger = DecisionLogger(self.config.get("decisions_log_max", 100))
        self.dry_run = dry_run
        self.confirm = confirm
        self.decisions_made: List[Decision] = []
    
    def should_cleanup(self) -> tuple:
        """判断是否需要清理，返回 (是否需要, 原因)"""
        stats = self.lifecycle.check()
        to_archive = stats['to_archive']
        threshold = self.config.get("archive_threshold", 10)
        
        # 原因1：超过阈值
        if to_archive >= threshold:
            return True, f"待归档文件 {to_archive} >= 阈值 {threshold}"
        
        # 原因2：超过1天未清理且有待归档
        last_cleanup = self.config.get("last_cleanup")
        if last_cleanup and to_archive > 0:
            last = datetime.fromisoformat(last_cleanup)
            if (datetime.now() - last).days >= 1:
                return True, f"超过1天未清理，待归档文件 {to_archive} 个"
        
        return False, None
    
    def should_distill(self) -> tuple:
        """判断是否需要提炼，返回 (是否需要, 原因)"""
        last_distill = self.config.get("last_distill")
        distill_days = self.config.get("distill_days", 7)
        
        if not last_distill:
            return True, "从未执行过日志提炼"
        
        last = datetime.fromisoformat(last_distill)
        days_since = (datetime.now() - last).days
        
        if days_since >= distill_days:
            return True, f"距离上次提炼 {days_since} 天 >= {distill_days} 天阈值"
        
        return False, None
    
    def confirm_action(self, action: str, count: int) -> bool:
        """确认危险操作"""
        if self.dry_run:
            print(f"  🔍 [Dry-Run] 将执行: {action} ({count} 项)")
            return False
        
        if not self.confirm:
            response = input(f"  ⚠️ 确认执行 {action} ({count} 项)? [y/N]: ")
            if response.lower() != 'y':
                print(f"  ❌ 已取消")
                return False
        return True
    
    def execute_cleanup(self) -> Decision:
        """执行清理"""
        should, reason = self.should_cleanup()
        stats = self.lifecycle.check()
        count = stats['to_archive']
        
        decision = Decision("cleanup", reason)
        
        if not should:
            decision.result = "skipped"
            decision.details = {"reason": "不满足清理条件"}
            self.decisions_made.append(decision)
            return decision
        
        if not self.confirm_action("清理过期日志", count):
            decision.result = "cancelled"
            decision.details = {"cancelled_by_user": True}
            self.decisions_made.append(decision)
            return decision
        
        if self.dry_run:
            decision.result = "success"
            decision.details = {"dry_run": True, "would_archive": count}
            self.decisions_made.append(decision)
            return decision
        
        print("🧹 [Watchdog] 执行自动清理...")
        result = self.lifecycle.run_cleanup()
        
        self.config.set("last_cleanup", datetime.now().isoformat())
        
        decision.result = "success"
        decision.details = {
            "archived": result.get("archived", 0),
            "deleted": result.get("deleted", 0),
            "errors": result.get("errors", 0)
        }
        self.decisions_made.append(decision)
        self.decision_logger.add(decision)
        
        return decision
    
    def execute_distill(self) -> Decision:
        """执行日志提炼"""
        should, reason = self.should_distill()
        
        # 统计待提炼数量
        undistilled = []
        memory_dir = Path("/root/.openclaw/workspace/memory")
        today = datetime.now()
        for i in range(30):  # 检查最近30天
            d = today - timedelta(days=i)
            date_str = d.strftime("%Y-%m-%d")
            if (memory_dir / f"{date_str}.md").exists():
                if self.distiller.should_distill(date_str):
                    undistilled.append(date_str)
        
        count = len(undistilled)
        reason = f"{reason}，待提炼 {count} 个日志"
        
        decision = Decision("distill", reason)
        
        if not should:
            decision.result = "skipped"
            decision.details = {"reason": "不满足提炼条件"}
            self.decisions_made.append(decision)
            return decision
        
        if count == 0:
            decision.result = "skipped"
            decision.details = {"reason": "没有待提炼的日志"}
            self.decisions_made.append(decision)
            return decision
        
        if not self.confirm_action("提炼日志", count):
            decision.result = "cancelled"
            decision.details = {"cancelled_by_user": True}
            self.decisions_made.append(decision)
            return decision
        
        if self.dry_run:
            decision.result = "success"
            decision.details = {"dry_run": True, "would_distill": count, "dates": undistilled[:5]}
            self.decisions_made.append(decision)
            return decision
        
        print("📝 [Watchdog] 执行日志提炼...")
        
        results = []
        for d in undistilled[:5]:  # 最多5个
            result = self.distiller.distill(d)
            if result:
                results.append(result)
                self.distiller.mark_distilled(d)
        
        self.config.set("last_distill", datetime.now().isoformat())
        
        decision.result = "success"
        decision.details = {
            "distilled": len(results),
            "dates": undistilled[:5]
        }
        self.decisions_made.append(decision)
        self.decision_logger.add(decision)
        
        return decision
    
    def run_health_check(self) -> Decision:
        """执行健康检查"""
        decision = Decision("health_check", "例行健康检查")
        
        stats = {
            "memory_lifecycle": self.lifecycle.check(),
            "knowledge_graph": {
                "entities": len(self.kg.entities)
            },
            "rules": {
                "total": len(self.rm.rules),
                "active": len([r for r in self.rm.rules.values() if r.status == "active"])
            },
            "timestamp": datetime.now().isoformat()
        }
        
        decision.result = "success"
        decision.details = stats
        self.decisions_made.append(decision)
        
        return decision
    
    def should_run(self) -> tuple:
        """判断是否应该运行，返回 (是否需要, 原因)"""
        last_check = self.config.get("last_check")
        interval = self.config.get("check_interval_hours", 6)
        
        if not last_check:
            return True, "首次运行"
        
        last = datetime.fromisoformat(last_check)
        hours_since = (datetime.now() - last).total_seconds() / 3600
        
        if hours_since >= interval:
            return True, f"距离上次检查 {hours_since:.1f} 小时 >= {interval} 小时"
        
        return False, f"距离上次检查 {hours_since:.1f} 小时 < {interval} 小时，跳过"
    
    def run(self, force: bool = False):
        """运行看门狗"""
        should_run, run_reason = self.should_run()
        
        if not force and not should_run:
            print(f"⏰ [Watchdog] {run_reason}")
            return
        
        # 更新最后检查时间
        self.config.set("last_check", datetime.now().isoformat())
        
        print("=" * 80)
        print(f"🐕 Memory Watchdog - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   运行原因: {run_reason}")
        print("=" * 80)
        
        # 1. 健康检查
        self.run_health_check()
        
        # 2. 决策：是否需要清理
        cleanup_decision = self.execute_cleanup()
        
        # 3. 决策：是否需要提炼
        distill_decision = self.execute_distill()
        
        # 4. 保存所有决策到日志
        for decision in self.decisions_made:
            if decision.result != "skipped":  # 只保存执行的决策
                self.decision_logger.add(decision)
        
        # 5. 输出摘要
        self.print_summary()
        
        return self.decisions_made
    
    def print_summary(self):
        """打印执行摘要"""
        print("\n" + "=" * 80)
        print("📊 Watchdog 执行摘要")
        print("=" * 80)
        
        if self.dry_run:
            print("  🔍 模式: Dry-Run（模拟运行，不实际执行）")
        
        print("\n📋 决策记录:")
        for d in self.decisions_made:
            status_icon = {
                "success": "✅",
                "cancelled": "⏭️",
                "failed": "❌",
                "skipped": "⏭️"
            }.get(d.result, "•")
            print(f"\n  {status_icon} {d.action}")
            print(f"     原因: {d.reason}")
            if d.result:
                print(f"     结果: {d.result}")
        
        print("\n" + "=" * 80)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Memory Watchdog - 标准自动运维系统')
    parser.add_argument('--run', '-r', action='store_true', help='执行看门狗')
    parser.add_argument('--force', '-f', action='store_true', help='强制执行（忽略时间间隔）')
    parser.add_argument('--stats', '-s', action='store_true', help='显示状态')
    parser.add_argument('--log', '-l', action='store_true', help='显示决策日志')
    parser.add_argument('--log-n', type=int, default=10, help='显示最近N条决策日志')
    parser.add_argument('--set', nargs=2, metavar=('KEY', 'VALUE'), help='设置配置参数')
    parser.add_argument('--dry-run', '-n', action='store_true', help='模拟运行（不实际执行）')
    parser.add_argument('--confirm', '-y', action='store_true', help='跳过确认直接执行')
    args = parser.parse_args()
    
    # 配置管理
    cfg = WatchdogConfig()
    
    if args.set:
        key, value = args.set
        # 类型转换
        if value.isdigit():
            value = int(value)
        elif value.lower() == 'true':
            value = True
        elif value.lower() == 'false':
            value = False
        cfg.set(key, value)
        print(f"✅ 配置已更新: {key} = {value}")
        return
    
    if args.stats:
        print("📊 当前配置:")
        print(f"   archive_threshold: {cfg.get('archive_threshold')}")
        print(f"   distill_days: {cfg.get('distill_days')}")
        print(f"   check_interval_hours: {cfg.get('check_interval_hours')}")
        print(f"   auto_cleanup_enabled: {cfg.get('auto_cleanup_enabled')}")
        print(f"   last_check: {cfg.get('last_check') or '从未'}")
        print(f"   last_cleanup: {cfg.get('last_cleanup') or '从未'}")
        print(f"   last_distill: {cfg.get('last_distill') or '从未'}")
        
        # 健康检查
        print("\n🏥 健康检查:")
        lifecycle = LifecycleManager()
        stats = lifecycle.check()
        print(f"   记忆文件: {stats['active_files']} 活跃")
        print(f"   待归档: {stats['to_archive']}")
        
        kg = KnowledgeGraph()
        print(f"   知识图谱实体: {len(kg.entities)}")
        
        rm = RuleManager()
        print(f"   活跃规则: {len([r for r in rm.rules.values() if r.status == 'active'])}/{len(rm.rules)}")
        return
    
    if args.log:
        dl = DecisionLogger()
        dl.print_log(args.log_n)
        return
    
    # 文件锁防止多实例同时运行
    lock_fd = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print(f"⏰ [Watchdog] 另一个实例正在运行，跳过")
        return
    
    watchdog = MemoryWatchdog(dry_run=args.dry_run, confirm=args.confirm)
    
    if args.run or args.force or (not args.stats and not args.log):
        watchdog.run(force=args.force)
    elif args.dry_run:
        watchdog.run(force=True)
    
    fcntl.flock(lock_fd, fcntl.LOCK_UN)
    lock_fd.close()

if __name__ == '__main__':
    main()
