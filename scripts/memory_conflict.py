#!/usr/bin/env python3
"""
Memory Conflict Detector - 事件驱动冲突检测

核心思路（坤哥建议）：
  不要定期扫描 + LLM判断（太贵太慢）
  → 在写入时检测（事件驱动）

实现：
  def add_memory(new_memory):
      conflicts = search_similar(new_memory)
      for m in conflicts:
          if is_conflict(m, new_memory):
              resolve(m, new_memory)

冲突类型：
  - preference conflict（用户偏好）
  - factual conflict（事实）
  - strategy conflict（策略）

解决策略：
  1. 保留高置信度
  2. 时间优先（新覆盖旧）
  3. 标记冲突（供推理使用）
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional

# ============ 冲突类型定义 ============

class ConflictType:
    PREFERENCE = "preference"   # 用户偏好冲突
    FACTUAL = "factual"         # 事实冲突
    STRATEGY = "strategy"       # 策略冲突
    UNKNOWN = "unknown"


# ============ 冲突检测规则 ============

class ConflictDetector:
    """
    冲突检测器（轻量级规则引擎，无需 LLM）
    """
    
    # 偏好关键词
    PREFERENCE_PATTERNS = [
        r"喜欢", r"不喜欢", r"偏好", r"倾向",
        r"要", r"不要", r"必须", r"应该",
        r"从来", r"总是", r"从不", r"一般"
    ]
    
    # 事实关键词
    FACTUAL_PATTERNS = [
        r"是", r"不是", r"有", r"没有",
        r"在", r"不在", r"位于", r"等于",
        r"台", r"台服务器", r"个", r"只",
    ]
    
    # 策略关键词
    STRATEGY_PATTERNS = [
        r"用", r"不用", r"改用", r"换成",
        r"方案", r"策略", r"做法", r"流程",
        r"每天", r"每周", r"定期"
    ]
    
    # 否定词
    NEGATIONS = ["不", "没", "非", "无", "别", "禁止", "不再"]
    
    # 冲突连接词
    CONTRAST_CONNECTORS = ["但是", "然而", "不过", "可是", "却"]
    
    def detect_type(self, text: str) -> str:
        """检测记忆类型"""
        for pattern in self.PREFERENCE_PATTERNS:
            if re.search(pattern, text):
                return ConflictType.PREFERENCE
        for pattern in self.FACTUAL_PATTERNS:
            if re.search(pattern, text):
                return ConflictType.FACTUAL
        for pattern in self.STRATEGY_PATTERNS:
            if re.search(pattern, text):
                return ConflictType.STRATEGY
        return ConflictType.UNKNOWN
    
    def has_negation(self, text: str) -> bool:
        """是否有否定词"""
        return any(neg in text for neg in self.NEGATIONS)
    
    def extract_key_claims(self, text: str) -> set:
        """
        提取关键主张（去掉否定后的核心词）
        用于判断两条记忆是否矛盾
        """
        text_clean = text.lower()
        for neg in self.NEGATIONS:
            text_clean = text_clean.replace(neg, "")
        # 提取中文词
        words = re.findall(r'[\u4e00-\u9fff]+', text_clean)
        # 过滤停用词
        stopwords = {"的", "是", "在", "和", "了", "有", "我", "你", "他", "她", "它"}
        return {w for w in words if w not in stopwords and len(w) >= 2}
    
    def is_conflict(self, mem1: dict, mem2: dict) -> Tuple[bool, str]:
        """
        判断两条记忆是否冲突
        
        Returns:
            (is_conflict: bool, reason: str)
        """
        type1, type2 = mem1.get("type"), mem2.get("type")
        content1, content2 = mem1.get("content", ""), mem2.get("content", "")
        
        # 1. 类型相同 + 一个肯定一个否定
        if type1 == type2:
            neg1, neg2 = self.has_negation(content1), self.has_negation(content2)
            if neg1 != neg2:
                # 提取核心主张
                claims1 = self.extract_key_claims(content1)
                claims2 = self.extract_key_claims(content2)
                overlap = claims1 & claims2
                if overlap:
                    return True, f"类型相同({type1})，主张重叠{overlap}，一肯定一否定"
        
        # 2. 偏好冲突（倾向相反）
        if type1 == type2 == ConflictType.PREFERENCE:
            neg1, neg2 = self.has_negation(content1), self.has_negation(content2)
            if neg1 != neg2:
                return True, "偏好倾向相反"
        
        # 3. 事实冲突（数字/实体不同）
        if type1 == type2 == ConflictType.FACTUAL:
            # 检查数字冲突
            nums1 = set(re.findall(r'\d+', content1))
            nums2 = set(re.findall(r'\d+', content2))
            if nums1 and nums2 and nums1 != nums2:
                return True, f"事实数字冲突: {nums1} vs {nums2}"
            
            # 检查实体冲突
            claims1 = self.extract_key_claims(content1)
            claims2 = self.extract_key_claims(content2)
            # 如果有重叠主张但结论矛盾
            if claims1 & claims2:
                # 检查是否有"是/在" vs "不是/不在"
                if ("是" in content1) != ("是" in content2):
                    return True, "事实判断冲突"
        
        # 4. 策略冲突（新策略 vs 旧策略）
        if type1 == type2 == ConflictType.STRATEGY:
            if ("用" in content1) != ("用" in content2):
                return True, "策略做法冲突"
            # 新旧时间对比
            time_kws = ["现在", "以后", "之后", "改为"]
            old_kws = ["以前", "之前", "原来"]
            has_new = any(kw in content2 for kw in time_kws)
            has_old = any(kw in content1 for kw in old_kws)
            if has_new or has_old:
                return True, "策略更新（旧被新替代）"
        
        return False, ""


# ============ 冲突解决策略 ============

class ConflictResolver:
    """
    冲突解决器
    """
    
    STRATEGY_HIGH_CONF = "high_confidence"  # 保留高置信度
    STRATEGY_NEWER = "newer_wins"            # 新覆盖旧
    STRATEGY_MARK = "mark_pending"           # 标记待裁决
    
    def resolve(self, mem1: dict, mem2: dict, 
                strategy: str = "auto") -> Dict:
        """
        解决冲突
        
        Args:
            mem1, mem2: 两条冲突的记忆
            strategy: 解决策略
                - "auto": 自动（高置信度优先）
                - "newer_wins": 新的覆盖旧的
                - "keep_both": 保留两条但标记
                - "user": 标记待用户裁决
        
        Returns:
            {
                "resolved": bool,
                "action": str,  # "delete_1" / "delete_2" / "keep_both" / "pending"
                "kept": str,   # 保留的记忆ID
                "deleted": str, # 删除的记忆ID
                "reason": str
            }
        """
        conf1, conf2 = mem1.get("importance", 0.5), mem2.get("importance", 0.5)
        time1 = mem1.get("timestamp", "")
        time2 = mem2.get("timestamp", "")
        
        if strategy == "auto":
            # 策略1：置信度优先
            if abs(conf1 - conf2) > 0.2:
                if conf1 > conf2:
                    return self._resolve_delete(mem2, mem1, f"置信度更高({conf1:.2f} > {conf2:.2f})")
                else:
                    return self._resolve_delete(mem1, mem2, f"置信度更高({conf2:.2f} > {conf1:.2f})")
            
            # 策略2：时间优先（新覆盖旧）
            if time1 and time2:
                try:
                    t1 = datetime.fromisoformat(time1)
                    t2 = datetime.fromisoformat(time2)
                    if t2 > t1:
                        return self._resolve_delete(mem1, mem2, "新记忆覆盖旧记忆")
                    else:
                        return self._resolve_delete(mem2, mem1, "新记忆覆盖旧记忆")
                except:
                    pass
            
            # 策略3：都保留但标记
            return self._mark_both(mem1, mem2, "置信度相近，时间无法判断")
        
        elif strategy == "newer_wins":
            if time2 > time1:
                return self._resolve_delete(mem1, mem2, "新覆盖旧")
            else:
                return self._resolve_delete(mem2, mem1, "新覆盖旧")
        
        elif strategy == "keep_both":
            return self._mark_both(mem1, mem2, "保留两条")
        
        else:  # user
            return {
                "resolved": False,
                "action": "pending_user",
                "kept": None,
                "deleted": None,
                "reason": "需用户裁决"
            }
    
    def _resolve_delete(self, to_delete: dict, to_keep: dict, reason: str) -> Dict:
        return {
            "resolved": True,
            "action": "delete",
            "kept": to_keep["id"],
            "deleted": to_delete["id"],
            "reason": reason
        }
    
    def _mark_both(self, mem1: dict, mem2: dict, reason: str) -> Dict:
        return {
            "resolved": True,
            "action": "mark_both",
            "kept": mem1["id"],
            "deleted": mem2["id"],
            "reason": reason,
            "conflict_type": "pending_review"
        }


# ============ Event-Driven Conflict Manager ============

class ConflictManager:
    """
    事件驱动冲突管理器
    
    核心：在写入时检测冲突，无需定期扫描
    """
    
    def __init__(self, memory_manager):
        self.memory = memory_manager
        self.detector = ConflictDetector()
        self.resolver = ConflictResolver()
        self._conflict_log: List[Dict] = []
    
    def add_with_conflict_check(self, content: str, type: str = "observation",
                                 importance: float = 0.5, tags: List[str] = None,
                                 **kwargs) -> Dict:
        """
        写入记忆（带冲突检测）
        
        流程：
        1. 搜索相似记忆
        2. 检测是否有冲突
        3. 解决冲突
        4. 写入新记忆
        5. 返回操作报告
        """
        report = {
            "new_memory_id": None,
            "conflicts_found": [],
            "resolved": [],
            "pending": []
        }
        
        # 1. 先写入（获取ID）
        new_id = self.memory.add(content, type, importance, tags, **kwargs)
        new_mem = self.memory.get(new_id)
        report["new_memory_id"] = new_id
        
        # 2. 搜索相似记忆
        similar = self.memory.search(content, top_k=5)
        similar = [m for m in similar if m.id != new_id]
        
        if not similar:
            return report
        
        # 3. 检测冲突
        for existing in similar:
            is_conf, reason = self.detector.is_conflict(
                {"id": existing.id, "content": existing.content, "type": existing.type,
                 "importance": existing.importance, "timestamp": existing.timestamp},
                {"id": new_mem.id, "content": new_mem.content, "type": new_mem.type,
                 "importance": new_mem.importance, "timestamp": new_mem.timestamp}
            )
            
            if is_conf:
                conflict = {
                    "existing_id": existing.id,
                    "new_id": new_id,
                    "reason": reason
                }
                report["conflicts_found"].append(conflict)
                
                # 4. 自动解决
                resolution = self.resolver.resolve(
                    existing.to_dict() if hasattr(existing, 'to_dict') else existing,
                    new_mem.to_dict() if hasattr(new_mem, 'to_dict') else new_mem,
                    strategy="auto"
                )
                
                if resolution["resolved"]:
                    if resolution["action"] == "delete":
                        self.memory.delete(resolution["deleted"])
                    elif resolution["action"] == "mark_both":
                        self.memory.update(resolution["deleted"], 
                                        tags=["conflict_pending"])
                    
                    report["resolved"].append({
                        **conflict,
                        **resolution
                    })
                else:
                    # 标记待裁决
                    self.memory.update(new_id, tags=["conflict_pending"])
                    self.memory.update(existing.id, tags=["conflict_pending"])
                    report["pending"].append(conflict)
        
        # 记录到冲突日志
        if report["conflicts_found"]:
            self._conflict_log.append({
                "time": datetime.now().isoformat(),
                "new_id": new_id,
                "conflicts": report["conflicts_found"]
            })
        
        return report
    
    def get_conflict_log(self) -> List[Dict]:
        """获取冲突历史"""
        return self._conflict_log


# ============ 轻量级版本（独立使用）============

class SimpleConflictManager:
    """
    独立使用的简单冲突管理器
    不依赖 MemoryManager，可单独使用
    """
    
    def __init__(self, storage_path: str = "/tmp/.conflict_memories.json"):
        self.storage_path = Path(storage_path)
        self.detector = ConflictDetector()
        self.resolver = ConflictResolver()
        self._memories: List[Dict] = []
        self._conflict_log: List[Dict] = []
        self._load()
    
    def _load(self):
        if self.storage_path.exists():
            with open(self.storage_path) as f:
                data = json.load(f)
                self._memories = data.get("memories", [])
                self._conflict_log = data.get("log", [])
    
    def _save(self):
        with open(self.storage_path, "w") as f:
            json.dump({
                "memories": self._memories,
                "log": self._conflict_log[-100:]  # 只保留最近100条
            }, f, indent=2, ensure_ascii=False)
    
    def add(self, content: str, type: str = "observation",
            importance: float = 0.5, tags: List[str] = None,
            timestamp: str = None) -> str:
        """
        添加记忆（事件驱动冲突检测）
        """
        mid = f"mem_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        new_mem = {
            "id": mid,
            "content": content,
            "type": type,
            "importance": importance,
            "timestamp": timestamp or datetime.now().isoformat(),
            "tags": tags or []
        }
        
        report = {"conflicts_found": [], "resolved": []}
        
        # 搜索相似
        query_lower = content.lower()
        similar = [
            m for m in self._memories
            if query_lower in m["content"].lower()
        ][:5]
        
        # 检测冲突
        for existing in similar:
            is_conf, reason = self.detector.is_conflict(existing, new_mem)
            if is_conf:
                report["conflicts_found"].append({
                    "existing_id": existing["id"],
                    "new_id": mid,
                    "reason": reason
                })
                
                resolution = self.resolver.resolve(existing, new_mem)
                if resolution["resolved"]:
                    if resolution["action"] == "delete":
                        self._memories = [m for m in self._memories if m["id"] != resolution["deleted"]]
                    elif resolution["action"] == "mark_both":
                        for m in self._memories:
                            if m["id"] in [existing["id"], new_mem["id"]]:
                                m["tags"] = m.get("tags", []) + ["conflict_pending"]
                    
                    report["resolved"].append(resolution)
        
        self._memories.append(new_mem)
        self._save()
        report["new_memory_id"] = mid
        return report
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        query_lower = query.lower()
        results = [m for m in self._memories if query_lower in m["content"].lower()]
        results.sort(key=lambda x: x.get("importance", 0), reverse=True)
        return results[:top_k]
    
    def get_conflicts(self) -> List[Dict]:
        return [m for m in self._memories if "conflict_pending" in m.get("tags", [])]


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Memory Conflict Detector")
    parser.add_argument("--add", "-a", metavar="CONTENT", help="添加记忆")
    parser.add_argument("--type", "-t", choices=["preference", "factual", "strategy", "observation"],
                       default="observation", help="记忆类型")
    parser.add_argument("--importance", "-i", type=float, default=0.5, help="重要性")
    parser.add_argument("--search", "-s", metavar="QUERY", help="搜索")
    parser.add_argument("--conflicts", action="store_true", help="显示冲突记忆")
    args = parser.parse_args()
    
    manager = SimpleConflictManager()
    
    if args.add:
        result = manager.add(args.add, args.type, args.importance)
        print(f"添加: {result['new_memory_id']}")
        if result['conflicts_found']:
            print(f"发现 {len(result['conflicts_found'])} 个冲突:")
            for c in result['conflicts_found']:
                print(f"  - {c['reason']}")
        if result['resolved']:
            print(f"解决 {len(result['resolved'])} 个冲突:")
            for r in result['resolved']:
                print(f"  - {r['action']}: {r.get('reason', '')}")
    
    elif args.search:
        results = manager.search(args.search)
        print(f"搜索 '{args.search}': {len(results)} 条")
        for m in results:
            tags = f" [{','.join(m.get('tags',[]))}]" if m.get('tags') else ""
            print(f"  - [{m['type']}] {m['content'][:50]}... (imp={m['importance']}){tags}")
    
    elif args.conflicts:
        conflicts = manager.get_conflicts()
        print(f"冲突记忆 ({len(conflicts)} 条):")
        for m in conflicts:
            print(f"  - {m['content'][:60]}...")


if __name__ == "__main__":
    main()
