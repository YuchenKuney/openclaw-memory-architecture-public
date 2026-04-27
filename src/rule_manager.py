#!/usr/bin/env python3
"""
Rule Manager - 规则管理系统

功能：
1. 从日志中提取规则
2. 规则分类（偏好/行为/错误）
3. 置信度计算
4. 规则合并
5. 规则淘汰
"""

import os
import re
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

MEMORY_DIR = Path("/root/.openclaw/workspace/memory")
RULES_DIR = Path("/root/.openclaw/workspace/rules")
CONFIG_FILE = Path("/root/.openclaw/workspace/.rules.json")

class Rule:
    def __init__(self, text: str, category: str, source: str = None):
        self.id = hashlib.md5(text[:50].encode()).hexdigest()[:8]
        self.text = text
        self.category = category  # preference | behavior | error
        self.source = source or datetime.now().strftime("%Y-%m-%d")
        self.confidence = 0.5
        self.usage_count = 0
        self.success_count = 0
        self.last_used = None
        self.created_at = datetime.now().isoformat()
        self.status = "active"
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "category": self.category,
            "source": self.source,
            "confidence": round(self.confidence, 3),
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "last_used": self.last_used,
            "created_at": self.created_at,
            "status": self.status
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> 'Rule':
        r = cls(d["text"], d["category"], d.get("source"))
        r.id = d["id"]
        r.confidence = d.get("confidence", 0.5)
        r.usage_count = d.get("usage_count", 0)
        r.success_count = d.get("success_count", 0)
        r.last_used = d.get("last_used")
        r.created_at = d.get("created_at", datetime.now().isoformat())
        r.status = d.get("status", "active")
        return r
    
    def use(self, success: bool = True):
        """使用规则"""
        self.usage_count += 1
        self.last_used = datetime.now().strftime("%Y-%m-%d")
        if success:
            self.success_count += 1
        self.recalculate_confidence()
    
    def recalculate_confidence(self):
        """重新计算置信度"""
        # 成功率 (0.6 weight)
        success_rate = self.success_count / self.usage_count if self.usage_count > 0 else 0
        success_score = success_rate * 0.6
        
        # 来源权威性 (0.3 weight)
        source_score = 0.5  # 默认中等
        if self.source:
            try:
                source_date = datetime.strptime(self.source, "%Y-%m-%d")
                days_ago = (datetime.now() - source_date).days
                if days_ago <= 7:
                    source_score = 1.0
                elif days_ago <= 30:
                    source_score = 0.7
                else:
                    source_score = 0.4
            except:
                pass
        
        # 时效性 (0.1 weight)
        time_score = 0.5
        if self.last_used:
            try:
                last_date = datetime.strptime(self.last_used, "%Y-%m-%d")
                days_ago = (datetime.now() - last_date).days
                if days_ago <= 7:
                    time_score = 1.0
                elif days_ago <= 30:
                    time_score = 0.7
                else:
                    time_score = 0.3
            except:
                pass
        
        self.confidence = min(1.0, success_score + source_score * 0.3 + time_score * 0.1)
    
    def should_deprecate(self) -> bool:
        """是否应该淘汰"""
        if self.confidence < 0.3:
            return True
        if self.status == "deprecated":
            return True
        # 90天未使用
        if self.last_used:
            try:
                last_date = datetime.strptime(self.last_used, "%Y-%m-%d")
                if (datetime.now() - last_date).days > 90:
                    return True
            except:
                pass
        return False

class RuleManager:
    CATEGORY_PATTERNS = {
        "preference": ["喜欢", "偏好", "坤哥要", "坤哥说", "希望", "不要"],
        "behavior": ["每天", "定时", "定期", "每次", "流程", "规则"],
        "error": ["⚠️", "教训", "错误", "失败", "不能", "禁止", "小心"]
    }
    
    def __init__(self):
        self.rules: Dict[str, Rule] = {}
        self.config = self.load_config()
        self.load_rules()
    
    def load_config(self) -> dict:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        return {"rules": {}}
    
    def save_config(self):
        rules_data = {rid: r.to_dict() for rid, r in self.rules.items()}
        self.config["rules"] = rules_data
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def load_rules(self):
        for rid, rdata in self.config.get("rules", {}).items():
            self.rules[rid] = Rule.from_dict(rdata)
    
    def classify(self, text: str) -> str:
        """分类文本"""
        for cat, patterns in self.CATEGORY_PATTERNS.items():
            for p in patterns:
                if p in text:
                    return cat
        return "behavior"  # 默认行为规则
    
    def extract_rules_from_log(self, content: str, source_date: str) -> List[Rule]:
        """从日志中提取规则"""
        rules = []
        
        # 提取教训/警告
        lesson_patterns = [
            r'⚠️?\s*[教训经验发现].*?[:：]\s*(.+)',
            r'⚠️?\s*[注意警告].*?[:：]\s*(.+)',
            r'[规则铁律].*?[:：]\s*(.+)',
            r'([一二三]、.+)',  # 列表格式
        ]
        
        for pattern in lesson_patterns:
            matches = re.findall(pattern, content)
            for m in matches:
                if len(m) > 10:
                    text = m.strip()
                    # 检查是否已存在
                    existing = self.find_similar(text)
                    if not existing:
                        category = self.classify(text)
                        rule = Rule(text, category, source_date)
                        rule.confidence = 0.6  # 初始置信度
                        rules.append(rule)
        
        return rules
    
    def find_similar(self, text: str) -> Optional[Rule]:
        """查找相似规则"""
        text_hash = hashlib.md5(text[:50].encode()).hexdigest()[:8]
        for rule in self.rules.values():
            if rule.id == text_hash:
                return rule
            # 简单相似度检查
            if text[:30] in rule.text or rule.text[:30] in text:
                return rule
        return None
    
    def add_rule(self, rule: Rule):
        """添加规则"""
        self.rules[rule.id] = rule
        self.save_config()
    
    def merge_rules(self, category: str = None, keep: str = "highest_confidence"):
        """合并同类规则
        
        Args:
            category: 指定分类，不指定则处理所有
            keep: 'highest_confidence' 保留最高置信度 | 'newest' 保留最新
        """
        if category:
            cats = [category]
        else:
            cats = ["preference", "behavior", "error"]
        
        for cat in cats:
            cat_rules = [r for r in self.rules.values() if r.category == cat and r.status == "active"]
            # 按文本相似度分组
            groups = []
            for rule in cat_rules:
                found = False
                for g in groups:
                    if any(rule.text[:40] in r.text or r.text[:40] in rule.text for r in g):
                        g.append(rule)
                        found = True
                        break
                if not found:
                    groups.append([rule])
            
            # 合并每组：只保留一个
            for g in groups:
                if len(g) > 1:
                    if keep == "highest_confidence":
                        g.sort(key=lambda x: x.confidence, reverse=True)
                    else:  # newest
                        g.sort(key=lambda x: x.last_used or x.source or "", reverse=True)
                    
                    winner = g[0]
                    # 标记其他为deprecated
                    for r in g[1:]:
                        r.status = "deprecated"
                        print(f"  合并 {len(g)} 条 -> 保留: [{winner.category}] "
                              f"置信度={winner.confidence:.2f} | {winner.text[:40]}...")
        
        self.save_config()
    
    def cleanup_rules(self):
        """清理低置信度规则"""
        deprecated = []
        for rule in self.rules.values():
            if rule.should_deprecate():
                rule.status = "deprecated"
                deprecated.append(rule)
        
        if deprecated:
            print(f"  标记 {len(deprecated)} 条规则为deprecated")
        else:
            print("  无需清理")
        
        self.save_config()
        return deprecated
    
    def use_rule(self, rule_id: str, success: bool = True):
        """使用规则"""
        if rule_id in self.rules:
            self.rules[rule_id].use(success)
            self.save_config()
    
    def get_active_rules(self, category: str = None) -> List[Rule]:
        """获取活跃规则"""
        rules = [r for r in self.rules.values() if r.status == "active"]
        if category:
            rules = [r for r in rules if r.category == category]
        return sorted(rules, key=lambda x: x.confidence, reverse=True)
    
    def print_rules(self, category: str = None):
        """打印规则"""
        rules = self.get_active_rules(category)
        
        print("=" * 60)
        print("📋 规则列表")
        print("=" * 60)
        
        for cat, cat_name in [("preference", "⭐ 用户偏好"), 
                              ("behavior", "🔧 行为规则"),
                              ("error", "⚠️ 错误教训")]:
            cat_rules = [r for r in rules if r.category == cat]
            if not cat_rules:
                continue
            print(f"\n{cat_name} ({len(cat_rules)}):")
            for r in cat_rules:
                conf_bar = "█" * int(r.confidence * 10) + "░" * (10 - int(r.confidence * 10))
                print(f"  [{conf_bar}] P{r.usage_count} {r.text[:50]}...")
        
        print("=" * 60)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Rule Manager - 规则管理系统')
    parser.add_argument('--extract', '-e', metavar='DATE', help='从指定日志提取规则')
    parser.add_argument('--check', '-c', action='store_true', help='检查规则状态')
    parser.add_argument('--merge', '-m', choices=['confidence', 'newest'], 
                        const='confidence', nargs='?', help='合并同类规则 (confidence=保留最高置信度, newest=保留最新)')
    parser.add_argument('--cleanup', action='store_true', help='清理低置信度规则')
    parser.add_argument('--list', '-l', metavar='CATEGORY', help='列出规则 (preference/behavior/error)')
    args = parser.parse_args()
    
    manager = RuleManager()
    
    if args.extract:
        filepath = MEMORY_DIR / f"{args.extract}.md"
        if not filepath.exists():
            print(f"日志不存在: {args.extract}.md")
            return
        with open(filepath, 'r') as f:
            content = f.read()
        rules = manager.extract_rules_from_log(content, args.extract)
        print(f"从 {args.extract} 提取了 {len(rules)} 条规则:")
        for r in rules:
            print(f"  [{r.category}] {r.text[:60]}")
            manager.add_rule(r)
    
    elif args.check:
        manager.print_rules()
    
    elif args.merge:
        keep = args.merge if args.merge else "confidence"
        print(f"合并同类规则 (保留策略: {keep})...")
        manager.merge_rules(keep=keep)
    
    elif args.cleanup:
        print("清理低置信度规则...")
        manager.cleanup_rules()
    
    elif args.list:
        manager.print_rules(args.list)
    
    else:
        manager.print_rules()

if __name__ == '__main__':
    main()
