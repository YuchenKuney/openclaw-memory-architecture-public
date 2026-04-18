#!/usr/bin/env python3
"""
Memory Auditor - 记忆审计与矛盾检测

功能：
- 定期扫描记忆库，检测矛盾对
- 标记冲突项，由用户裁决或自动解决
- 输出审计报告
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional

MEMORY_DIR = Path("/root/.openclaw/workspace/memory")
BELIEFS_FILE = Path("/root/.openclaw/workspace/.beliefs.json")
AUDIT_LOG = Path("/root/.openclaw/workspace/.memory_audit_log.json")

# 矛盾关键词对（同时出现可能表示矛盾）
CONTRADICTION_PAIRS = [
    ("必须", "不需要"),
    ("应该", "不应该"),
    ("喜欢", "不喜欢"),
    ("使用", "不再使用"),
    ("从来", "有时"),
    ("总是", "偶尔"),
    ("所有", "部分"),
    ("从不", "偶尔"),
    ("一直", "有时"),
]

# 反义关键词
NEGATION_KEYWORDS = [
    "不", "没", "非", "无", "别", "禁止", "停止", "取消"
]

class MemoryAuditor:
    """记忆审计器"""
    
    def __init__(self):
        self.audit_log = self._load_log()
    
    def _load_log(self) -> List[Dict]:
        if AUDIT_LOG.exists():
            with open(AUDIT_LOG) as f:
                return json.load(f)
        return []
    
    def _save_log(self):
        with open(AUDIT_LOG, "w") as f:
            json.dump(self.audit_log, f, indent=2, ensure_ascii=False)
    
    def _extract_rules(self, text: str) -> List[str]:
        """从文本中提取规则性语句"""
        rules = []
        lines = text.replace("。", "\n").replace("；", "\n").split("\n")
        for line in lines:
            line = line.strip()
            if len(line) < 5 or len(line) > 200:
                continue
            # 包含规则特征的语句
            if any(kw in line for kw in ["必须", "应该", "不要", "记得", "重要", "规则"]):
                rules.append(line)
        return rules
    
    def _check_contradiction_pair(self, rule1: str, rule2: str) -> bool:
        """检查两条规则是否矛盾"""
        # 检查否定关键词的存在
        def has_negation(rule):
            return any(kw in rule for kw in NEGATION_KEYWORDS)
        
        # 两条规则一个肯定一个否定
        if has_negation(rule1) != has_negation(rule2):
            # 检查核心词是否相同
            words1 = set(rule1.replace("不", "").replace("没", ""))
            words2 = set(rule2.replace("不", "").replace("没", ""))
            # 有重叠词但一个有否定一个没有
            overlap = words1 & words2
            if overlap and len(overlap) >= 2:
                return True
        return False
    
    def _scan_beliefs(self) -> List[Dict]:
        """扫描信念库，检测矛盾"""
        if not BELIEFS_FILE.exists():
            return []
        
        with open(BELIEFS_FILE) as f:
            data = json.load(f)
        
        beliefs = list(data.get("beliefs", {}).values())
        conflicts = []
        
        # 两两对比
        for i, b1 in enumerate(beliefs):
            for b2 in beliefs[i+1:]:
                # 同类型才可能矛盾
                if b1.get("category") != b2.get("category"):
                    continue
                
                text1 = b1.get("text", "")
                text2 = b2.get("text", "")
                
                # 检查否定对
                if self._check_contradiction_pair(text1, text2):
                    conflicts.append({
                        "type": "negation",
                        "belief1": {"id": b1.get("id"), "text": text1[:80], "confidence": b1.get("confidence")},
                        "belief2": {"id": b2.get("id"), "text": text2[:80], "confidence": b2.get("confidence")},
                        "category": b1.get("category")
                    })
                
                # 检查数字或事实矛盾
                # 例如：服务器有3台 vs 服务器有5台（简化版）
                # 这里只做简单的关键词重叠检测
                words1 = set(text1.lower().split())
                words2 = set(text2.lower().split())
                overlap = words1 & words2
                if len(overlap) >= 3:  # 共享3个以上词
                    # 检查是否有矛盾修饰词
                    mods1 = [w for w in words1 if w in ["所有", "每个", "全部"] or w.endswith("都")]
                    mods2 = [w for w in words2 if w in ["所有", "每个", "全部"] or w.endswith("都")]
                    if mods1 and mods2 and mods1 != mods2:
                        # 都是"所有"类，但描述对象不同
                        pass  # 简化处理
                
                # 检查时间矛盾
                time_kws = ["之前", "之后", "现在", "以前", "以后"]
                t1 = [kw for kw in time_kws if kw in text1]
                t2 = [kw for kw in time_kws if kw in text2]
                if t1 and t2 and t1 != t2:
                    # 时间描述矛盾
                    conflicts.append({
                        "type": "temporal",
                        "belief1": {"id": b1.get("id"), "text": text1[:80], "confidence": b1.get("confidence")},
                        "belief2": {"id": b2.get("id"), "text": text2[:80], "confidence": b2.get("confidence")},
                        "category": b1.get("category")
                    })
        
        return conflicts
    
    def _scan_memory_files(self) -> List[Dict]:
        """扫描每日日志，检测矛盾"""
        conflicts = []
        
        if not MEMORY_DIR.exists():
            return conflicts
        
        # 收集所有规则性语句
        all_rules = {}
        for f in MEMORY_DIR.glob("2026-*.md"):
            try:
                date = f.stem[:10]
                with open(f) as fp:
                    for rule in self._extract_rules(fp.read()):
                        key = rule[:30].lower()
                        if key not in all_rules:
                            all_rules[key] = []
                        all_rules[key].append({"date": date, "text": rule})
            except:
                continue
        
        # 找矛盾对
        rule_list = list(all_rules.items())
        for i, (k1, rules1) in enumerate(rule_list):
            for k2, rules2 in rule_list[i+1:]:
                for r1 in rules1:
                    for r2 in rules2:
                        if self._check_contradiction_pair(r1["text"], r2["text"]):
                            conflicts.append({
                                "type": "memory_contradiction",
                                "rule1": {"date": r1["date"], "text": r1["text"][:80]},
                                "rule2": {"date": r2["date"], "text": r2["text"][:80]},
                                "category": "behavior"
                            })
        
        return conflicts
    
    def audit(self) -> Dict:
        """
        执行完整审计
        返回审计报告
        """
        belief_conflicts = self._scan_beliefs()
        memory_conflicts = self._scan_memory_files()
        
        all_conflicts = belief_conflicts + memory_conflicts
        
        report = {
            "audit_time": datetime.now().isoformat(),
            "total_conflicts": len(all_conflicts),
            "belief_conflicts": len(belief_conflicts),
            "memory_conflicts": len(memory_conflicts),
            "conflicts": all_conflicts[:20],  # 最多返回20条
            "needs_attention": len(all_conflicts) > 0
        }
        
        # 记录审计
        self.audit_log.append({
            "time": datetime.now().isoformat(),
            "conflicts_found": len(all_conflicts)
        })
        # 只保留最近100条审计记录
        self.audit_log = self.audit_log[-100:]
        self._save_log()
        
        return report
    
    def format_report(self, report: Dict) -> str:
        """格式化审计报告"""
        lines = [
            "=" * 60,
            "📋 Memory Audit Report - 记忆审计报告",
            "=" * 60,
            f"审计时间: {report['audit_time']}",
            f"总矛盾数: {report['total_conflicts']}",
            f"  - 信念矛盾: {report['belief_conflicts']}",
            f"  - 日志矛盾: {report['memory_conflicts']}",
            ""
        ]
        
        if not report['conflicts']:
            lines.append("✅ 未发现明显矛盾")
        else:
            lines.append("⚠️ 发现以下潜在矛盾:\n")
            for i, c in enumerate(report['conflicts'], 1):
                lines.append(f"--- 矛盾 {i} ({c.get('type')}) ---")
                if "belief1" in c:
                    lines.append(f"  信念A (置信度 {c['belief1'].get('confidence', 0):.0%}): {c['belief1']['text']}")
                    lines.append(f"  信念B (置信度 {c['belief2'].get('confidence', 0):.0%}): {c['belief2']['text']}")
                elif "rule1" in c:
                    lines.append(f"  规则A ({c['rule1']['date']}): {c['rule1']['text']}")
                    lines.append(f"  规则B ({c['rule2']['date']}): {c['rule2']['text']}")
                lines.append("")
        
        lines.append("=" * 60)
        return "\n".join(lines)
    
    def auto_resolve(self, conflict: Dict) -> Optional[str]:
        """
        自动解决矛盾（保守策略）
        - 置信度差距 > 20% → 保留高置信度
        - 否则标记待用户裁决
        返回解决策略描述
        """
        if "confidence" not in str(conflict):
            return "标记待裁决（需人工判断）"
        
        c1 = conflict.get("belief1", {}).get("confidence", 0.5)
        c2 = conflict.get("belief2", {}).get("confidence", 0.5)
        
        if abs(c1 - c2) > 0.2:
            winner = "belief1" if c1 > c2 else "belief2"
            loser = "belief2" if c1 > c2 else "belief1"
            return f"保留: {conflict[winner]['text'][:50]}... (置信度更高)"
        else:
            return "标记待裁决（置信度相近，需人工判断）"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Memory Auditor - 记忆审计与矛盾检测")
    parser.add_argument("--audit", "-a", action="store_true", help="执行审计")
    parser.add_argument("--show-log", "-l", action="store_true", help="显示审计历史")
    parser.add_argument("--resolve", "-r", metavar="CONFLICT_IDX", type=int,
                        help="自动解决指定矛盾")
    args = parser.parse_args()
    
    auditor = MemoryAuditor()
    
    if args.audit:
        report = auditor.audit()
        print(auditor.format_report(report))
    
    elif args.show_log:
        print("📜 审计历史记录:")
        for entry in auditor.audit_log[-10:]:
            print(f"  {entry['time']}: 发现 {entry['conflicts_found']} 个矛盾")
    
    elif args.resolve is not None:
        report = auditor.audit()
        if args.resolve < len(report['conflicts']):
            conflict = report['conflicts'][args.resolve]
            resolution = auditor.auto_resolve(conflict)
            print(f"解决策略: {resolution}")
        else:
            print("无效的矛盾索引")
    
    else:
        print("Memory Auditor - 记忆审计与矛盾检测")
        print("用法:")
        print("  --audit       执行审计")
        print("  --show-log    显示审计历史")
        print("  --resolve N   自动解决第N个矛盾")


if __name__ == "__main__":
    main()
