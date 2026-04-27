#!/usr/bin/env python3
"""
Daily Log Distiller - 每日日志提炼器
完整流程：完整日志 → 提炼精华 → 更新记忆 → 归档原日志

Usage:
    python3 daily_distiller.py --distill 2026-04-16    # 提炼指定日期
    python3 daily_distiller.py --recent 7              # 提炼最近7天
    python3 daily_distiller.py --full                   # 完整流程
"""

import re
import os
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

MEMORY_DIR = Path("/root/.openclaw/workspace/memory")
ARCHIVE_DIR = Path("/root/.openclaw/workspace/memory/archive")
MEMORY_FILE = Path("/root/.openclaw/workspace/MEMORY.md")
CONFIG_FILE = Path("/root/.openclaw/workspace/.distiller.json")

class DailyDistiller:
    def __init__(self):
        self.memory_dir = MEMORY_DIR
        self.config = self.load_config()
    
    def load_config(self) -> dict:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        return {
            "last_distill": None,
            "distilled_dates": [],
            "extracted_knowledge": []
        }
    
    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def extract_by_section(self, content: str) -> Dict:
        """按section提取"""
        result = {
            "reminders": [],      # 重要提醒
            "tasks_done": [],     # 已完成任务
            "tasks_pending": [],  # 待完成任务
            "decisions": [],      # 决策
            "lessons": [],        # 教训/经验
            "technical": [],      # 技术信息
            "knowledge": []       # 可沉淀的知识
        }
        
        lines = content.split('\n')
        current_section = None
        
        for line in lines:
            # 检测section
            if line.startswith('## '):
                current_section = line[3:].strip().lower()
                continue
            
            # 按section分类提取
            if current_section:
                if '提醒' in current_section or '重要' in current_section:
                    if line.strip().startswith('-'):
                        result["reminders"].append(line.strip())
                elif '任务' in current_section:
                    if '[x]' in line.lower() or '✅' in line:
                        result["tasks_done"].append(line.strip())
                    elif line.strip().startswith('-'):
                        result["tasks_pending"].append(line.strip())
                elif '决策' in current_section or '完成' in current_section:
                    if line.strip().startswith(('1.', '2.', '3.', '✅', '-')):
                        result["decisions"].append(line.strip())
                elif '教训' in current_section or '备注' in current_section:
                    if line.strip().startswith('-'):
                        result["lessons"].append(line.strip())
                elif '技术' in current_section or '配置' in current_section:
                    if line.strip().startswith('-'):
                        result["technical"].append(line.strip())
        
        # 额外提取：代码块中的路径和命令
        paths = re.findall(r'`([^`]+)`', content)
        result["technical"].extend(paths)
        
        # 提取URL
        urls = re.findall(r'https?://[^\s]+', content)
        result["knowledge"].extend(urls)
        
        return result
    
    def distill_date(self, date: str) -> Optional[Dict]:
        """提炼指定日期的日志"""
        filepath = self.memory_dir / f"{date}.md"
        if not filepath.exists():
            print(f"⚠️ 日志不存在: {date}.md")
            return None
        
        with open(filepath, 'r') as f:
            content = f.read()
        
        extracted = self.extract_by_section(content)
        
        return {
            "date": date,
            "extracted": extracted,
            "raw_length": len(content),
            "summary": self.generate_summary(date, extracted)
        }
    
    def generate_summary(self, date: str, extracted: Dict) -> str:
        """生成精华摘要"""
        lines = [f"### {date}\n"]
        
        if extracted["tasks_done"]:
            lines.append("**完成:** " + ", ".join([
                t.replace('-', '').strip()[:50] for t in extracted["tasks_done"][:3]
            ]))
        
        if extracted["decisions"]:
            lines.append("**决策:** " + "; ".join([
                d.strip()[:60] for d in extracted["decisions"][:3]
            ]))
        
        if extracted["lessons"]:
            lines.append("**教训:** " + "; ".join([
                l.replace('-', '').strip()[:60] for l in extracted["lessons"][:3]
            ]))
        
        if not lines:
            lines.append(f"完成了日常任务，未产生需要沉淀的知识。")
        
        return "\n".join(lines)
    
    def generate_memory_update(self, distill_results: List[Dict]) -> str:
        """生成需要更新到记忆的内容"""
        lines = ["\n## 日志提炼（自动生成）\n"]
        lines.append(f"*提炼日期: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")
        
        for r in distill_results:
            lines.append(r["summary"])
            lines.append("")
        
        # 添加到记忆的指导
        lines.append("---")
        lines.append("\n**操作:** 上述内容应选择性添加到 MEMORY.md 或 shared/ 目录")
        
        return "\n".join(lines)
    
    def get_recent_dates(self, n: int) -> List[str]:
        """获取最近n天的日期"""
        dates = []
        today = datetime.now()
        for i in range(n):
            d = today - timedelta(days=i)
            date_str = d.strftime("%Y-%m-%d")
            # 检查日志是否存在
            if (self.memory_dir / f"{date_str}.md").exists():
                dates.append(date_str)
        return dates
    
    def distill_recent(self, days: int = 7) -> List[Dict]:
        """提炼最近n天的日志"""
        dates = self.get_recent_dates(days)
        results = []
        for d in dates:
            if d not in self.config["distilled_dates"]:
                r = self.distill_date(d)
                if r:
                    results.append(r)
        return results
    
    def mark_distilled(self, date: str, result: Dict):
        """标记已提炼"""
        if date not in self.config["distilled_dates"]:
            self.config["distilled_dates"].append(date)
        
        self.config["extracted_knowledge"].append({
            "date": date,
            "summary": result["summary"]
        })
        self.config["last_distill"] = datetime.now().isoformat()
        self.save_config()
    
    def run_full_workflow(self, days: int = 7):
        """完整流程：提炼 → 展示更新建议"""
        print("=" * 60)
        print("📝 Daily Distiller - 完整日志提炼流程")
        print("=" * 60)
        
        # 1. 提炼
        results = self.distill_recent(days)
        if not results:
            print("✅ 没有新的日志需要提炼")
            return
        
        print(f"\n📊 提炼了 {len(results)} 天的日志:\n")
        for r in results:
            print(f"  📅 {r['date']} ({r['raw_length']} 字符)")
        
        # 2. 生成更新建议
        print("\n" + "=" * 60)
        print("📤 建议更新到记忆的内容:")
        print("=" * 60)
        update = self.generate_memory_update(results)
        print(update)
        
        # 3. 标记已提炼
        for r in results:
            self.mark_distilled(r["date"], r)
        
        print("\n✅ 提炼完成！")
        print("   记忆系统未自动更新，请手动审查后添加。")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Daily Log Distiller')
    parser.add_argument('--date', '-d', help='指定日期 (YYYY-MM-DD)')
    parser.add_argument('--recent', '-r', type=int, default=0, help='最近n天')
    parser.add_argument('--full', '-f', action='store_true', help='完整流程')
    args = parser.parse_args()
    
    distiller = DailyDistiller()
    
    if args.full or (not args.date and args.recent == 0):
        distiller.run_full_workflow(7)
    elif args.date:
        result = distiller.distill_date(args.date)
        if result:
            print(result["summary"])
    elif args.recent > 0:
        results = distiller.distill_recent(args.recent)
        for r in results:
            print(r["summary"])
            print()

if __name__ == '__main__':
    main()
