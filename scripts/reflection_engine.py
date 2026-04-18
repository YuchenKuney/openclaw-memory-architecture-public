#!/usr/bin/env python3
"""
Reflection Engine - 反思引擎（Memory Ownership 版）

✅ 接管后：所有读取走 MemoryManager.search()
  ❌ 接管前：直接读 /root/.openclaw/workspace/memory/*.md
  ✅ 接管后：memory_manager.search()，由它路由到正确后端

借鉴 Generative Agents (Park et al., 2023) 的反思机制
"""

import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional

MEMORY_DIR = Path("/root/.openclaw/workspace/memory")
BELIEFS_FILE = Path("/root/.openclaw/workspace/.beliefs.json")


# ============ MemoryStream（统一读取）============

class MemoryStream:
    """
    记忆流

    ✅ 接管后：接受 MemoryManager，所有读取走 manager.search()
    ✅ 接管前（兼容）：直接读文件
    """

    def __init__(self, days: int = 7, memory_manager=None):
        self.days = days
        self.memory_manager = memory_manager
        self.memories = []
        self.load_recent()

    def load_recent(self):
        """加载最近 N 天的记忆"""
        cutoff = datetime.now() - timedelta(days=self.days)
        self.memories = []

        if self.memory_manager:
            # ✅ 走统一入口：MemoryManager.search()
            items = self.memory_manager.search(
                query="",
                top_k=50,
                router="recent"
            )
            for item in items:
                try:
                    item_time = datetime.fromisoformat(item.timestamp)
                    if item_time < cutoff:
                        continue
                    date_str = item_time.strftime("%Y-%m-%d")
                    self.memories.append({
                        "date": date_str,
                        "content": item.content,
                        "id": item.id,
                        "type": item.type
                    })
                except:
                    continue
        else:
            # 降级：直接读文件（兼容旧逻辑）
            if not MEMORY_DIR.exists():
                return
            for f in sorted(MEMORY_DIR.glob("2026-*.md"), reverse=True):
                try:
                    date_str = f.stem[:10]
                    fdate = datetime.strptime(date_str, "%Y-%m-%d")
                    if fdate < cutoff:
                        continue
                    with open(f) as fp:
                        self.memories.append({
                            "date": date_str,
                            "content": fp.read(),
                            "path": str(f)
                        })
                except:
                    continue

        self.memories.sort(key=lambda x: x["date"])

    def get_recent_text(self, limit_chars: int = 5000) -> str:
        """获取合并后的最近记忆文本"""
        parts = []
        total = 0
        for m in reversed(self.memories):
            if total + len(m["content"]) > limit_chars:
                break
            parts.append(f"=== {m['date']} ===\n{m['content']}")
            total += len(m["content"])
        return "\n\n".join(parts)

    def get_recent_items(self, limit: int = 20) -> List[Dict]:
        """返回原始记忆条目（供反思使用）"""
        items = []
        for m in reversed(self.memories):
            items.append(m)
            if len(items) >= limit:
                break
        return items


# ============ Belief =====================

class Belief:
    def __init__(self, id: str, text: str, category: str,
                 confidence: float = 0.5, source_count: int = 1):
        self.id = id
        self.text = text
        self.category = category
        self.confidence = min(1.0, confidence)
        self.source_count = source_count
        self.last_updated = datetime.now().isoformat()
        self.last_verified = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id, "text": self.text, "category": self.category,
            "confidence": self.confidence, "source_count": self.source_count,
            "last_updated": self.last_updated, "last_verified": self.last_verified
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'Belief':
        b = cls(d["id"], d["text"], d["category"],
                d.get("confidence", 0.5), d.get("source_count", 1))
        b.last_updated = d.get("last_updated", datetime.now().isoformat())
        b.last_verified = d.get("last_verified", datetime.now().isoformat())
        return b

    def verify(self, success: bool):
        if success:
            self.confidence = min(1.0, self.confidence + 0.1)
            self.source_count += 1
        else:
            self.confidence = max(0.1, self.confidence - 0.15)
        self.last_verified = datetime.now().isoformat()

    def strengthen(self):
        self.confidence = min(1.0, self.confidence + 0.05)
        self.last_updated = datetime.now().isoformat()


# ============ BeliefStore（统一读取）============

class BeliefStore:
    """
    信念库

    ✅ 接管后：接受 MemoryManager，读写都通过它
    """

    def __init__(self, memory_manager=None):
        self.memory_manager = memory_manager
        self.beliefs: Dict[str, Belief] = {}
        self._load()

    def _load(self):
        if not BELIEFS_FILE.exists():
            return
        try:
            with open(BELIEFS_FILE) as f:
                data = json.load(f)
                for bid, bdict in data.items():
                    self.beliefs[bid] = Belief.from_dict(bdict)
        except:
            pass

    def save(self):
        data = {bid: b.to_dict() for bid, b in self.beliefs.items()}
        with open(BELIEFS_FILE, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add_belief(self, text: str, category: str, confidence: float = 0.5) -> str:
        bid = f"belief_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.beliefs[bid] = Belief(bid, text, category, confidence)
        self.save()
        return bid

    def get_active(self) -> List[Belief]:
        return sorted(self.beliefs.values(),
                      key=lambda b: -b.confidence)

    def update_confidence(self, belief_id: str, delta: float):
        if belief_id in self.beliefs:
            b = self.beliefs[belief_id]
            b.confidence = min(1.0, max(0.1, b.confidence + delta))
            b.last_updated = datetime.now().isoformat()
            self.save()


# ============ ReflectionEngine =====================

class ReflectionEngine:
    """
    反思引擎

    ✅ 接管后：所有模块（MemoryStream/BeliefStore）都接受 MemoryManager
       所有读取走 manager.search()，所有写入走 manager.add()
    """

    def __init__(self, memory_manager=None):
        self.memory_manager = memory_manager
        self.stream = MemoryStream(days=7, memory_manager=memory_manager)
        self.beliefs = BeliefStore(memory_manager=memory_manager)

    def reflect(self, memory_text: str = None) -> Dict:
        """
        执行反思

        1. 从记忆流获取近期记忆
        2. 生成反思内容
        3. 更新信念库
        """
        if not memory_text:
            memory_text = self.stream.get_recent_text()

        insights = self._generate_insights(memory_text)
        new_beliefs = self._extract_beliefs(insights)

        result = {
            "insights": insights,
            "new_beliefs": new_beliefs,
            "total_beliefs": len(self.beliefs.get_active()),
            "memory_days": len(self.stream.memories)
        }

        # 如果有 memory_manager，写入也通过它
        if self.memory_manager and new_beliefs:
            for belief_text in new_beliefs:
                self.memory_manager.add(
                    content=f"[反思] {belief_text}",
                    type="belief",
                    importance=0.7,
                    source="reflection_engine"
                )

        return result

    def _generate_insights(self, memory_text: str) -> List[str]:
        insights = []
        lines = memory_text.split("\n")
        counter = {}
        for line in lines:
            words = re.findall(r'[\u4e00-\u9fff]+', line)
            for w in words:
                if len(w) >= 3:
                    counter[w] = counter.get(w, 0) + 1
        high_freq = [(w, c) for w, c in counter.items() if c >= 3]
        for word, count in sorted(high_freq, key=lambda x: -x[1])[:5]:
            insights.append(f"高频词「{word}」（出现{count}次）")
        return insights

    def _extract_beliefs(self, insights: List[str]) -> List[str]:
        new = []
        for insight in insights:
            bid = self.beliefs.add_belief(insight, category="trend", confidence=0.5)
            new.append(insight)
        return new


# ============ 兼容性别厂 ============

def create_engine(memory_manager=None):
    """工厂函数：创建带 MemoryManager 的引擎"""
    return ReflectionEngine(memory_manager=memory_manager)
