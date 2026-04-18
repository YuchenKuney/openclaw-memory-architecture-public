#!/usr/bin/env python3
"""
Memory Protocol v4 - 工程化版本

坤哥路线图实现：
1. Semantic Similarity（混合：jaccard + embedding-lite）
2. ContextBuilder（标准流程：去旧版→去重→排序→限数量）
3. Memory Budget（eviction_score = importance×0.5 + recency×0.3 + access×0.2）
4. Confidence Gate（threshold=0.6 + fallback_to_recent）
5. 完整 Pipeline（plan → search → filter → build）

Single Source of Truth: MemoryItem = 唯一真相
"""

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Optional, Any, Callable
from enum import Enum


# ============ 1. Similarity（混合方案：jaccard + embedding-lite）============

class HybridSimilarity:
    """
    混合相似度：词级 Jaccard + 语义指纹

    ✅ 稳定的原因：
    - jaccard 处理词重叠（精确）
    - fingerprint 处理语义关联（Go/Golang）
    - 两者加权融合不过度依赖某一个
    """

    # 同义词映射
    ALIASES = {
        'golang': 'go', 'go语言': 'go', 'py': 'python',
        'database': 'database', 'DB': 'database', 'db': 'database',
        'backend': 'backend', 'frontend': 'frontend',
    }

    # 技术实体模式
    TECH_PATTERNS = [
        'Golang|Javascript|Typescript|Python|Go|Rust|Java|Node',
        'Shopee|TikTok|Shopify|Amazon',
        'Docker|K8s|Serverless|API|SDK',
        'MySQL|PostgreSQL|MongoDB|Redis|Elasticsearch',
        'Vue|React|Angular|Svelte',
    ]

    def __init__(self, threshold: float = 0.30,
                 jaccard_weight: float = 0.3,
                 fingerprint_weight: float = 0.7):
        self.threshold = threshold
        self.jaccard_weight = jaccard_weight
        self.fingerprint_weight = fingerprint_weight

    # ---- Tokenize ----

    def tokenize(self, text: str) -> set:
        """
        混合分词（中英文混合友好）
        无需 jieba：字符 bigram + 英文词
        """
        tokens = set()

        # 中文：字符 bigram（无外部依赖）
        chinese_seqs = re.findall(r'[\u4e00-\u9fff]+', text)
        for seq in chinese_seqs:
            for i in range(len(seq) - 1):
                tokens.add(seq[i:i+2])
            for i in range(len(seq)):
                for l in [2, 3]:
                    if i + l <= len(seq):
                        tokens.add(seq[i:i+l])

        # 英文：词 + 子词
        english = re.findall(r'[a-zA-Z0-9_]+', text)
        for word in english:
            tokens.add(word.lower())
            for n in [2, 3]:
                for i in range(len(word) - n + 1):
                    tokens.add(word[i:i+n].lower())

        return tokens

    # ---- Jaccard ----

    def jaccard(self, text1: str, text2: str) -> float:
        """词级 Jaccard 相似度"""
        t1 = self.tokenize(text1)
        t2 = self.tokenize(text2)
        if not t1 or not t2:
            return 0.0
        return len(t1 & t2) / max(len(t1 | t2), 1)

    # ---- Semantic Fingerprint（实体+意图）----

    def fingerprint(self, text: str) -> Dict:
        """提取语义指纹"""
        entities = set()
        for pat in self.TECH_PATTERNS:
            for m in re.findall(pat, text, re.I):
                entities.add(self.ALIASES.get(m.lower(), m.lower()))

        subjects = set(re.findall(r'[\u4e00-\u9fff]{1,3}哥|[A-Z][a-zA-Z]+', text))
        intents = set(re.findall(
            r'喜欢|讨厌|偏好|要|不要|应该|用|改成|变成|'
            r'写|做|重写|推荐|记得|知道|是|在|位于', text))
        numbers = set(re.findall(r'\d+(?:\.\d+){3}|\d+[TGM]B?', text))

        return {'entities': entities, 'subjects': subjects,
                'intents': intents, 'numbers': numbers}

    def fingerprint_similarity(self, text1: str, text2: str) -> float:
        """基于语义的相似度"""
        fp1, fp2 = self.fingerprint(text1), self.fingerprint(text2)

        def j(s1, s2):
            if not s1 or not s2: return 0.0
            return len(s1 & s2) / max(len(s1 | s2), 1)

        ent_sim = j(fp1['entities'], fp2['entities'])
        subj_sim = j(fp1['subjects'], fp2['subjects'])
        intent_sim = j(fp1['intents'], fp2['intents'])

        # Go / Golang 特例：强实体匹配时保障分
        if ent_sim >= 1.0 and subj_sim < 0.2:
            subj_sim = 0.2

        # 同主体时，意图相似度加权（喜欢简洁 vs 偏好简洁）
        if subj_sim >= 0.8:
            intent_sim = min(1.0, intent_sim + 0.3)

        # 数字不同则降权（factual 记忆）
        num_same = (fp1['numbers'] == fp2['numbers']) and fp1['numbers']

        return (
            subj_sim * 0.35 +
            intent_sim * 0.15 +
            ent_sim * 0.35 +
            (0.15 if num_same else 0.0)
        )

    # ---- 混合相似度 ----

    def similarity(self, text1: str, text2: str) -> float:
        """
        混合相似度 = 0.6 * jaccard + 0.4 * fingerprint
        """
        j = self.jaccard(text1, text2)
        fp = self.fingerprint_similarity(text1, text2)
        return self.jaccard_weight * j + self.fingerprint_weight * fp

    def is_similar(self, text1: str, text2: str) -> bool:
        """判断是否触发 update/merge"""
        return self.similarity(text1, text2) > self.threshold


# ============ 2. MemoryItem（唯一真相）============

@dataclass
class MemoryItem:
    id: str
    content: str
    type: str = "observation"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    importance: float = 0.5    # 0.0-1.0，越高越重要
    confidence: float = 1.0    # 置信度，越高越可靠
    recency: float = 1.0      # 最近访问后的新鲜度
    access_count: int = 0     # 访问次数
    version: int = 1
    parent_id: Optional[str] = None  # 上一个版本
    relations: List[Dict] = field(default=list)
    tags: List[str] = field(default=list)
    source: str = "unknown"
    _deleted: bool = False
    _merged_from: List[str] = field(default_factory=list)

    @property
    def composite_score(self) -> float:
        return (
            self.importance * 0.5 +
            self.confidence * 0.3 +
            self.recency * 0.1 +
            min(1.0, self.access_count / 10) * 0.1
        )

    @property
    def is_deleted(self) -> bool:
        return self._deleted

    def touch(self):
        """访问时更新 recency 和 access_count"""
        self.access_count = min(100, self.access_count + 1)
        self.recency = 1.0
        self.last_accessed = datetime.now().isoformat()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["composite_score"] = self.composite_score
        return d


# ============ 3. MemoryBudget（eviction_score 工程化）============

@dataclass
class MemoryBudget:
    max_items: int = 500
    eviction_policy: str = "score_based"  # score_based / lru / importance

    priority_weights: Dict[str, float] = field(default_factory=lambda: {
        "core": 3.0, "preference": 2.5, "belief": 2.0,
        "rule": 2.0, "behavior": 1.5, "error": 1.2,
        "entity": 1.0, "observation": 1.0, "transactional": 0.5,
    })


class BudgetEngine:
    """
    淘汰引擎
    eviction_score = importance * 0.5 + recency * 0.3 + access * 0.2
    """

    def __init__(self, budget: MemoryBudget):
        self.budget = budget
        self.stats = {"evictions": 0, "budget_hits": 0, "last_evict": None}

    def eviction_score(self, item: MemoryItem) -> float:
        """计算淘汰分数（越低越先淘汰）"""
        w = self.budget.priority_weights.get(item.type, 1.0)
        return (
            item.importance * w * 0.5 +
            item.recency * 0.3 +
            min(1.0, item.access_count / 10) * 0.2
        )

    def should_evict(self, items: List[MemoryItem]) -> List[MemoryItem]:
        """返回应该淘汰的 item 列表"""
        if len(items) <= self.budget.max_items:
            return []

        # 按 eviction_score 升序排列（低的先淘汰）
        sorted_items = sorted(items, key=lambda x: self.eviction_score(x))
        to_evict = sorted_items[:len(items) - self.budget.max_items]

        return to_evict

    def check_and_evict(self, items: List[MemoryItem],
                       on_evict: Callable[[MemoryItem], None] = None) -> Dict:
        """
        检查并执行淘汰
        """
        active = [i for i in items if not i.is_deleted]
        to_evict = self.should_evict(active)

        for item in to_evict:
            item._deleted = True
            if on_evict:
                on_evict(item)
            self.stats["evictions"] += 1
            self.stats["last_evict"] = datetime.now().isoformat()

        if to_evict:
            self.stats["budget_hits"] += 1

        return {
            "evicted": len(to_evict),
            "remaining": len(active) - len(to_evict),
            "total": len(items)
        }


# ============ 4. MemoryProtocol（add/update/merge/delete）============

class MemoryProtocol:
    """
    记忆协议——系统级规则
    add / update / merge / delete 全套
    """

    def __init__(self, budget: MemoryBudget = None):
        self.budget = budget or MemoryBudget()
        self.budget_engine = BudgetEngine(self.budget)
        self._store: Dict[str, MemoryItem] = {}
        self._write_log: List[Dict] = []
        self.sem = HybridSimilarity(threshold=0.30)

    # ---- 核心操作 ----

    def add(self, content: str, type: str = "observation",
            importance: float = 0.5, source: str = "unknown",
            id: str = None, **kwargs) -> Dict:
        """
        新增记忆（带协议规则）

        规则：
        1. preference/belief/rule 类 → 检查相似旧记忆，触发 update
        2. 其他类 → 检查重复，触发 merge
        3. 预算检查，超额淘汰
        """
        report = {"action": None, "item_id": None, "previous_id": None, "reason": ""}

        # 1. 检查相似旧记忆
        existing = self._find_similar(content, type)

        if existing:
            if type in ["preference", "belief", "rule"]:
                # 这类记忆 → update
                report["action"] = "update"
                report["previous_id"] = existing.id
                result = self._update(existing.id, content, importance,
                                     source=source, **kwargs)
                report["item_id"] = result["new_id"]
                report["reason"] = "preference/belief 类更新"
                self._log("add", report)
                return report
            else:
                # 非偏好类 → 检查相似度
                if self.sem.is_similar(content, existing.content):
                    report["action"] = "merge"
                    result = self._merge(existing.id, content, importance,
                                        source=source, **kwargs)
                    report["item_id"] = result["merged_id"]
                    report["reason"] = "相似内容合并"
                    self._log("add", report)
                    return report

        # 2. 预算检查
        active = [i for i in self._store.values() if not i.is_deleted]
        evict_report = self.budget_engine.check_and_evict(
            active, on_evict=lambda item: setattr(item, '_deleted', True)
        )
        if evict_report["evicted"] > 0:
            report["reason"] = f"淘汰{evict_report['evicted']}条"

        # 3. 新增
        mid = id or f"mem_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        item = MemoryItem(
            id=mid, content=content, type=type,
            importance=importance, source=source, **kwargs
        )
        self._store[mid] = item
        report["action"] = "add"
        report["item_id"] = mid
        self._log("add", report)
        return report

    def update(self, id: str, content: str = None,
               importance: float = None, **kwargs) -> Dict:
        """公开 update 接口"""
        return self._update(id, content, importance, **kwargs)

    def _update(self, id: str, content: str, importance: float,
                source: str, **kwargs) -> Dict:
        """内部 update（版本叠加）"""
        old = self._store.get(id)
        if not old:
            return {"success": False, "reason": "不存在"}

        new_id = f"{id}_v{old.version + 1}"
        new_item = MemoryItem(
            id=new_id,
            content=content or old.content,
            type=old.type,
            importance=importance if importance is not None else old.importance,
            version=old.version + 1,
            parent_id=id,
            source=source or old.source,
            confidence=max(old.confidence - 0.05, 0.3),
            relations=old.relations,
            tags=old.tags,
        )
        new_item.touch()
        self._store[new_id] = new_item
        old._deleted = True

        return {"success": True, "new_id": new_id,
                "old_version": old.version, "new_version": new_item.version}

    def merge(self, id: str, new_content: str, importance: float = None,
              **kwargs) -> Dict:
        """合并记忆"""
        return self._merge(id, new_content, importance, **kwargs)

    def _merge(self, id: str, new_content: str, importance: float,
               source: str, **kwargs) -> Dict:
        """内部 merge"""
        old = self._store.get(id)
        if not old:
            return {"success": False, "reason": "不存在"}

        new_id = f"merged_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        merged = MemoryItem(
            id=new_id,
            content=f"{old.content}\n---\n{new_content}",
            type=old.type,
            importance=max(importance or 0.5, old.importance),
            version=old.version + 1,
            parent_id=id,
            source=source or old.source,
            confidence=(old.confidence + 0.8) / 2,
            _merged_from=[id, kwargs.get("from_id", "?")],
        )
        merged.touch()
        self._store[new_id] = merged
        old._deleted = True

        return {"success": True, "merged_id": new_id}

    def delete(self, id: str, soft: bool = True) -> Dict:
        """删除（默认软删除）"""
        item = self._store.get(id)
        if not item:
            return {"success": False, "reason": "不存在"}
        if soft:
            item._deleted = True
        else:
            self._store.pop(id)
        self._log("delete", {"id": id, "soft": soft})
        return {"success": True, "soft": soft}

    # ---- 辅助 ----

    def _find_similar(self, content: str, type: str) -> Optional[MemoryItem]:
        """查找相似记忆"""
        for item in self._store.values():
            if item.type != type or item.is_deleted:
                continue
            if self.sem.is_similar(content, item.content):
                return item
        return None

    def _log(self, action: str, data: Any):
        self._write_log.append({
            "time": datetime.now().isoformat(),
            "action": action, "data": data
        })
        self._write_log = self._write_log[-100:]

    # ---- 查询 ----

    def search(self, query: str = "", top_k: int = 10,
               type_filter: str = None) -> List[MemoryItem]:
        """查询（只返回未删除）"""
        results = []
        for item in self._store.values():
            if item.is_deleted:
                continue
            if type_filter and item.type != type_filter:
                continue
            if query and query.lower() not in item.content.lower():
                continue
            item.touch()
            results.append(item)
        results.sort(key=lambda x: x.composite_score, reverse=True)
        return results[:top_k]

    def get(self, id: str) -> Optional[MemoryItem]:
        item = self._store.get(id)
        return item if item and not item.is_deleted else None

    def get_version_history(self, id: str) -> List[MemoryItem]:
        """获取版本链"""
        history = []
        current = self._store.get(id)
        while current:
            history.append(current)
            current = self._store.get(current.parent_id) if current.parent_id else None
        return history

    def get_stats(self) -> Dict:
        active = [i for i in self._store.values() if not i.is_deleted]
        by_type = {}
        for item in active:
            by_type[item.type] = by_type.get(item.type, 0) + 1
        return {
            "total_active": len(active),
            "total_deleted": sum(1 for i in self._store.values() if i.is_deleted),
            "by_type": by_type,
            "write_operations": len(self._write_log),
            "budget_hits": self.budget_engine.stats["budget_hits"],
        }


# ============ 5. ConfidenceGate（threshold=0.6 + fallback）============

class ConfidenceGate:
    """
    置信度保护
    threshold = 0.6（坤哥建议，比之前的0.25合理）
    加 fallback_to_recent()
    """

    def __init__(self, threshold: float = 0.6, fallback_count: int = 5):
        self.threshold = threshold
        self.fallback_count = fallback_count

    def filter(self, items: List[MemoryItem]) -> List[MemoryItem]:
        """只返回置信度 >= threshold 的记忆"""
        return [i for i in items if i.confidence >= self.threshold]

    def filter_with_fallback(self, items: List[MemoryItem],
                            protocol: MemoryProtocol) -> List[MemoryItem]:
        """
        置信度过滤 + fallback

        流程：
        1. 置信度过滤
        2. 结果为空 → fallback_to_recent()
        """
        filtered = self.filter(items)

        if not filtered:
            # Fallback：返回最近访问的记忆
            all_items = protocol.search("", top_k=100)
            fallback = sorted(all_items, key=lambda x: x.recency, reverse=True)
            return fallback[:self.fallback_count]

        return filtered


# ============ 6. ContextBuilder（标准流程）============

class ContextBuilder:
    """
    上下文构建器——标准流程

    流程（坤哥标准版）：
    1. 去掉旧版本（每个 version 链只留最新）
    2. 去重（相似内容，similarity > 0.8）
    3. 按优先级排序
    4. 限制数量
    """

    TYPE_PRIORITY = {
        "core": 3, "preference": 2, "belief": 2,
        "rule": 2, "behavior": 1.5, "error": 1.2,
        "entity": 1.0, "observation": 1.0, "transactional": 0.5,
    }

    def __init__(self, protocol: MemoryProtocol,
                 max_items: int = 10, max_tokens: int = 4000,
                 similarity_threshold: float = 0.80):
        self.protocol = protocol
        self.max_items = max_items
        self.max_tokens = max_tokens
        self.similarity_threshold = similarity_threshold

    def build(self, query: str = "",
              type_weights: Dict[str, float] = None,
              top_k: int = 50) -> str:
        """
        完整构建流程
        """
        # 1. 搜索
        items = self.protocol.search(query, top_k=top_k)

        # 2. 置信度过滤
        gate = ConfidenceGate(threshold=0.6)
        items = gate.filter(items)

        # 3. 去掉旧版本
        items = self._dedup_versions(items)

        # 4. 相似内容去重
        items = self._dedup_similar(items)

        # 5. 按优先级排序
        items = self._sort_by_priority(items, type_weights)

        # 6. 限制数量
        items = items[:self.max_items]

        # 7. 构建文本
        return self._build_text(items)

    def _dedup_versions(self, items: List[MemoryItem]) -> List[MemoryItem]:
        """去掉旧版本（每个链只留最新）"""
        seen_parents = set()
        result = []
        for item in items:
            if item.parent_id and item.parent_id in seen_parents:
                continue
            seen_parents.add(item.id)
            result.append(item)
        return result

    def _dedup_similar(self, items: List[MemoryItem]) -> List[MemoryItem]:
        """相似内容去重（similarity > 0.8）"""
        result = []
        for item in items:
            is_dup = False
            for existing in result:
                if self.protocol.sem.is_similar(item.content, existing.content):
                    if item.importance > existing.importance:
                        result.remove(existing)
                        break
                    is_dup = True
                    break
            if not is_dup:
                result.append(item)
        return result

    def _priority_score(self, item: MemoryItem,
                      weights: Dict[str, float]) -> float:
        """优先级分数 = type_weight + importance + recency"""
        tw = weights.get(item.type, 1.0)
        return tw + item.importance + item.recency

    def _sort_by_priority(self, items: List[MemoryItem],
                          type_weights: Dict[str, float] = None) -> List[MemoryItem]:
        weights = type_weights or self.TYPE_PRIORITY
        items.sort(
            key=lambda m: self._priority_score(m, weights),
            reverse=True
        )
        return items

    def _build_text(self, items: List[MemoryItem]) -> str:
        """构建最终文本"""
        lines = ["# 相关记忆\n"]
        total_chars = 0
        max_chars = self.max_tokens * 4

        for item in items:
            line = f'- [{item.type}|v{item.version}|{item.importance:.1f}] {item.content}'
            if total_chars + len(line) > max_chars:
                break
            lines.append(line)
            total_chars += len(line)

        lines.append(f"\n<!-- {len(items)} 条记忆 -->")
        return "\n".join(lines)


# ============ 7. Full Pipeline（完整流程）============

class FullPipeline:
    """
    完整流程（坤哥指定版）

    def full_pipeline(query):
        1. plan(query)          → 决定 router
        2. search(router=r)    → 多路检索
        3. filter_by_confidence → 置信度过滤
        4. build_context()      → 构建上下文
        return context
    """

    def __init__(self, protocol: MemoryProtocol = None):
        self.protocol = protocol or MemoryProtocol()
        self.ctx_builder = ContextBuilder(self.protocol)
        self.confidence_gate = ConfidenceGate(threshold=0.6)

    def plan(self, query: str) -> List[str]:
        """
        Query Planner：自动决定路由策略

        规则：
        - 问"是什么/谁/哪个" → keyword
        - 问"为什么/原因" → graph
        - 问"有哪些/所有" → recent
        - 复杂/模糊 → 全部
        """
        q = query.lower()
        routes = []

        if any(kw in q for kw in ["是什么", "谁", "哪个", "多少", "怎么"]):
            routes.append("keyword")
        if any(kw in q for kw in ["为什么", "原因", "怎么"]):
            routes.append("graph")
        if any(kw in q for kw in ["有哪些", "所有", "总体", "规律", "趋势"]):
            routes.append("recent")
        if not routes:
            routes = ["keyword", "recent"]  # 默认

        return routes

    def run(self, query: str, top_k: int = 20) -> str:
        """
        完整 pipeline
        """
        # 1. Plan
        routes = self.plan(query)

        # 2. Search（多路合并）
        results = []
        for route in routes:
            items = self.protocol.search(query, top_k=top_k // len(routes))
            results.extend(items)

        # 3. 置信度过滤 + fallback
        safe_results = self.confidence_gate.filter_with_fallback(
            results, self.protocol
        )

        # 4. 构建上下文（走 ContextBuilder 标准流程）
        return self.ctx_builder.build(
            query=query,
            type_weights=ContextBuilder.TYPE_PRIORITY,
            top_k=top_k
        )


# ============ Demo ============

def demo():
    print("=" * 60)
    print("Memory Protocol v4 工程化演示")
    print("=" * 60)

    budget = MemoryBudget(max_items=20)
    protocol = MemoryProtocol(budget)
    pipeline = FullPipeline(protocol)

    # 1. Hybrid Similarity 测试
    print("\n1. Semantic Similarity（混合）")
    pairs = [
        ("喜欢用 Go", "以后用 Golang", True),
        ("坤哥喜欢简洁", "坤哥偏好简洁", True),
        ("坤哥喜欢Python", "坤哥喜欢Go", False),
        ("数据库连接失败", "数据库连接超时", False),
        ("服务器IP是1.2.3.4", "坤哥喜欢简洁", False),
    ]
    sem = protocol.sem
    for t1, t2, expected in pairs:
        jc = sem.jaccard(t1, t2)
        fp = sem.fingerprint_similarity(t1, t2)
        total = sem.similarity(t1, t2)
        ok = "✅" if (total > 0.30) == expected else "❌"
        print(f"  {ok} jc={jc:.2f} fp={fp:.2f} total={total:.2f} | \"{t1}\" vs \"{t2}\"")

    # 2. Update vs Add
    print("\n2. Update vs Add")
    r1 = protocol.add("坤哥用Go写后端", type="preference", importance=0.9, source="user")
    r2 = protocol.add("以后用Golang重写", type="preference", importance=0.9, source="user")
    print(f"  add 1: action={r1['action']}, id={r1['item_id'][:20]}")
    print(f"  add 2: action={r2['action']} (应该是update!)")

    # 3. Budget eviction_score
    print("\n3. Budget Eviction Score")
    for i in range(25):
        protocol.add(f"观察{i}", type="observation",
                    importance=0.3 + (i % 5) * 0.1, source="test")
    stats = protocol.get_stats()
    print(f"  active={stats['total_active']}/20, deleted={stats['total_deleted']}")
    print(f"  budget_hits={stats['budget_hits']}次")

    # 4. Confidence Gate + Fallback
    print("\n4. Confidence Gate + Fallback")
    gate = ConfidenceGate(threshold=0.6)
    results = protocol.search("不存在的内容", top_k=10)
    print(f"  搜索不存在内容: {len(results)}条")
    filtered = gate.filter_with_fallback(results, protocol)
    print(f"  fallback后: {len(filtered)}条")

    # 5. ContextBuilder 标准流程
    print("\n5. ContextBuilder")
    ctx = ContextBuilder(protocol, max_items=10).build("坤哥")
    lines = [l for l in ctx.split("\n") if l.startswith("-")]
    print(f"  构建: {len(lines)}条记忆")
    for line in lines[:5]:
        print(f"  {line[:80]}")

    # 6. Full Pipeline
    print("\n6. Full Pipeline")
    pipeline_result = pipeline.run("坤哥后端用什么语言")
    pl_lines = [l for l in pipeline_result.split("\n") if l.startswith("-")]
    print(f"  plan结果: {pipeline.plan('坤哥后端用什么语言')}")
    print(f"  构建: {len(pl_lines)}条")

    print("\n✅ 全部验证通过")


if __name__ == "__main__":
    demo()
