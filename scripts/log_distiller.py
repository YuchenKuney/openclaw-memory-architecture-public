#!/usr/bin/env python3
"""
Log Distiller - 日志提炼器

完整日志 → 提炼精华 → 更新记忆 → 归档原日志

## 提炼标准

### 1. 信息价值判断
| 问题 | 动作 |
|------|------|
| 是否成功解决问题？ | 未解决 → 不沉淀 |
| 是否重复出现 ≥2次？ | 重复 → 沉淀为规则 |
| 是否用户偏好/关键配置？ | 是 → 沉淀到USER.md |

### 2. 使用频率
| 频率 | 动作 |
|------|------|
| 常用命令/流程 | 保留在记忆中 |
| 一次性的 | 归档删除 |

### 3. 正确性验证
- 技术命令必须验证可用性
- 路径必须验证存在性
- 配置必须验证正确性

### 4. 沉淀优先级
1. **P0** - 用户偏好、关键配置、硬规则
2. **P1** - 成功解决问题的方案
3. **P2** - 重复≥2次的工作流
4. **P3** - 一次性的教训

Usage:
    python3 log_distiller.py --distill 2026-04-16
    python3 log_distiller.py --recent 7
    python3 log_distiller.py --full
"""

import re
import os
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

MEMORY_DIR = Path("/root/.openclaw/workspace/memory")
SHARED_DOMAIN = Path("/root/.openclaw/workspace/shared/domain")
CONFIG_FILE = Path("/root/.openclaw/workspace/.distiller.json")

class LogDistiller:
    """日志提炼器"""
    
    # 沉淀优先级
    PRIORITY_P0 = ["偏好", "配置", "硬规则", "铁律"]
    PRIORITY_P1 = ["解决", "成功", "完成", "✅"]
    PRIORITY_P2 = ["重复", "≥2", "再次"]
    PRIORITY_P3 = ["教训", "失败", "错误", "⚠️"]
    
    def __init__(self):
        self.config = self.load_config()
    
    def load_config(self) -> dict:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        return {
            "distilled_dates": [],
            "frequency_counter": {},  # 使用频率统计
            "verified_commands": []
        }
    
    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def compute_priority(self, content: str) -> int:
        """计算沉淀优先级"""
        for kw in self.PRIORITY_P0:
            if kw in content:
                return 0  # P0
        for kw in self.PRIORITY_P1:
            if kw in content:
                return 1  # P1
        for kw in self.PRIORITY_P2:
            if kw in content:
                return 2  # P2
        for kw in self.PRIORITY_P3:
            if kw in content:
                return 3  # P3
        return 4  # 默认P4（低优先级）
    
    def is_repeated(self, content: str) -> bool:
        """检查是否重复出现"""
        # 检查哈希去重
        h = hashlib.md5(content[:200].encode()).hexdigest()[:12]
        if "frequency_counter" not in self.config:
            self.config["frequency_counter"] = {}
        if h in self.config["frequency_counter"]:
            count = self.config["frequency_counter"][h] + 1
            self.config["frequency_counter"][h] = count
            return count >= 2
        self.config["frequency_counter"][h] = 1
        return False
    
    def verify_command(self, cmd: str) -> bool:
        """验证命令是否可用"""
        if not cmd or len(cmd) < 3:
            return False
        # 只验证简单命令，不执行危险操作
        if any(dangerous in cmd for dangerous in ['rm -rf', 'dd', 'mkfs']):
            return False
        return True
    
    def verify_path(self, path: str) -> bool:
        """验证路径是否存在"""
        if not path:
            return False
        return os.path.exists(path)
    
    def extract_value_info(self, content: str) -> Dict:
        """提取价值信息"""
        result = {
            "is_solution": False,
            "is_repeated": False,
            "is_preference": False,
            "priority": 4,
            "needs_verification": [],
            "summary": ""
        }
        
        # 检查是否成功解决问题
        if any(kw in content for kw in ["解决", "修复", "完成", "✅"]):
            result["is_solution"] = True
        
        # 检查是否重复
        if self.is_repeated(content):
            result["is_repeated"] = True
        
        # 检查是否用户偏好
        if any(kw in content for kw in ["偏好", "喜欢", "坤哥说", "坤哥要"]):
            result["is_preference"] = True
        
        # 计算优先级
        result["priority"] = self.compute_priority(content)
        
        # 提取需要验证的内容
        paths = re.findall(r'/[a-zA-Z0-9_/.-]+', content)
        for p in paths[:5]:
            if not self.verify_path(p):
                result["needs_verification"].append(f"路径不存在: {p}")
        
        return result
    
    def extract_tasks(self, content: str) -> List[dict]:
        """提取任务"""
        tasks = []
        task_patterns = [
            r'-\s*\[?\s*\]\s*(.+)',
            r'\d+\.\s*(.+)',
            r'\*\s*(.+)',
        ]
        for pattern in task_patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            for m in matches:
                if len(m) > 10:
                    tasks.append({
                        "text": m.strip(),
                        "done": '[x]' in m.lower() or '✅' in m or '完成' in m
                    })
        return tasks
    
    def extract_decisions(self, content: str) -> List[str]:
        """提取决策"""
        decisions = []
        patterns = [
            r'[确认决定启用实施改进].+?:(.+)',
            r'关键决策[:：](.+)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, content)
            decisions.extend(matches)
        return decisions
    
    def extract_lessons(self, content: str) -> List[dict]:
        """提取教训/经验"""
        lessons = []
        patterns = [
            r'[教训经验发现学到].+?[:：](.+)',
            r'⚠️[:：](.+)',
            r'注意[:：](.+)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for m in matches:
                lessons.append({
                    "text": m.strip(),
                    "priority": self.compute_priority(m)
                })
        # 按优先级排序
        lessons.sort(key=lambda x: x["priority"])
        return lessons
    
    def distill(self, date: str) -> Optional[Dict]:
        """提炼指定日期的日志"""
        filepath = MEMORY_DIR / f"{date}.md"
        if not filepath.exists():
            return None
        
        with open(filepath, 'r') as f:
            content = f.read()
        
        value_info = self.extract_value_info(content)
        tasks = self.extract_tasks(content)
        decisions = self.extract_decisions(content)
        lessons = self.extract_lessons(content)
        
        return {
            "date": date,
            "tasks": tasks,
            "decisions": decisions,
            "lessons": lessons,
            "value_info": value_info,
            "raw_length": len(content)
        }
    
    def should_distill(self, date: str) -> bool:
        """判断是否需要提炼"""
        if date in self.config.get("distilled_dates", []):
            return False
        return True
    
    def mark_distilled(self, date: str):
        """标记已提炼"""
        if "distilled_dates" not in self.config:
            self.config["distilled_dates"] = []
        if date not in self.config["distilled_dates"]:
            self.config["distilled_dates"].append(date)
        self.save_config()
    
    def generate_summary(self, result: Dict) -> str:
        """生成精华摘要"""
        lines = [f"### {result['date']}"]
        
        # 价值信息
        vi = result['value_info']
        if vi['is_preference']:
            lines.append("⭐ **用户偏好**")
        elif vi['is_solution']:
            lines.append("✅ **问题已解决**")
        elif vi['is_repeated']:
            lines.append("🔄 **重复出现**")
        
        if vi['needs_verification']:
            lines.append("⚠️ **待验证:**")
            for v in vi['needs_verification']:
                lines.append(f"   - {v}")
        
        # 任务
        done_tasks = [t for t in result['tasks'] if t['done']]
        if done_tasks:
            lines.append(f"\n**完成:** {len(done_tasks)}个任务")
        
        # 决策
        if result['decisions']:
            lines.append(f"\n**决策:** {result['decisions'][0][:80]}")
        
        # 教训
        if result['lessons']:
            top_lesson = result['lessons'][0]
            lines.append(f"\n**教训:** {top_lesson['text'][:80]}")
        
        return "\n".join(lines)
    
    def print_distill(self, date: str):
        """打印提炼结果"""
        result = self.distill(date)
        
        if not result:
            print(f"日志不存在: {date}.md")
            return
        
        print("=" * 50)
        print(f"📝 日志提炼: {date}")
        print(f"   原文长度: {result['raw_length']} 字符")
        print("=" * 50)
        
        vi = result['value_info']
        print(f"\n⭐ 价值判断:")
        print(f"   优先级: P{vi['priority']}")
        print(f"   解决问题: {'是' if vi['is_solution'] else '否'}")
        print(f"   重复出现: {'是' if vi['is_repeated'] else '否'}")
        print(f"   用户偏好: {'是' if vi['is_preference'] else '否'}")
        
        if vi['needs_verification']:
            print(f"\n⚠️ 待验证:")
            for v in vi['needs_verification'][:3]:
                print(f"   - {v}")
        
        print(f"\n📋 任务 ({len(result['tasks'])}):")
        for t in result['tasks'][:5]:
            status = "✅" if t['done'] else "⏳"
            print(f"   {status} {t['text'][:60]}")
        
        print(f"\n🎯 决策 ({len(result['decisions'])}):")
        for d in result['decisions'][:3]:
            print(f"   • {d.strip()[:80]}")
        
        print(f"\n⚠️ 教训 ({len(result['lessons'])}):")
        for l in result['lessons'][:3]:
            print(f"   • [P{l['priority']}] {l['text'][:80]}")
        
        print()
        print("=" * 50)
        print("📤 建议:")
        if vi['priority'] <= 1:
            print("   → 应沉淀到记忆系统")
        elif vi['is_repeated']:
            print("   → 重复≥2次，应沉淀为规则")
        else:
            print("   → 低优先级，可归档")
        
        self.mark_distilled(date)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Log Distiller - 日志提炼器')
    parser.add_argument('--distill', '-d', metavar='DATE', help='提炼指定日期 (YYYY-MM-DD)')
    parser.add_argument('--recent', '-r', type=int, metavar='N', help='提炼最近N天')
    parser.add_argument('--full', '-f', action='store_true', help='完整流程（所有待提炼日志）')
    args = parser.parse_args()
    
    distiller = LogDistiller()
    
    if args.distill:
        distiller.print_distill(args.distill)
    elif args.recent:
        from datetime import timedelta
        today = datetime.now()
        for i in range(args.recent):
            d = today - timedelta(days=i)
            date_str = d.strftime("%Y-%m-%d")
            if distiller.should_distill(date_str):
                distiller.print_distill(date_str)
    elif args.full:
        # 找出所有未提炼的日志
        today = datetime.now()
        for i in range(30):  # 最多检查30天
            d = today - timedelta(days=i)
            date_str = d.strftime("%Y-%m-%d")
            if distiller.should_distill(date_str):
                result = distiller.distill(date_str)
                if result:
                    print(distiller.generate_summary(result))
                    print()
    else:
        # 默认今天
        today = datetime.now().strftime("%Y-%m-%d")
        distiller.print_distill(today)

if __name__ == '__main__':
    main()
