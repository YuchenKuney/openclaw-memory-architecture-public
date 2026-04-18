#!/usr/bin/env python3
"""
Memory Pager - 核心版：双重真实信号驱动

核心洞察（来自坤哥）：
  retrieval_miss_rate ↑ 和 response_latency ↑ 
  比 token 计数更真实——这是模型自己"体感"到的变慢

三重触发（重新定义优先级）：
  PRIMARY（模型体感信号）:
    1. retrieval_miss_rate  ↑  — 搜不到想要的记忆
    2. response_latency     ↑  — 模型推理变慢
  
  SECONDARY（容量预警）:
    3. context_pressure      — 上下文占比高（确认信号）

只有 PRIMARY 信号才是真正的"需要换页"，
context_length 只是辅助判断内存碎片化程度。
"""

import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from collections import deque

MEMORY_DIR = Path("/root/.openclaw/workspace/memory")
ARCHIVAL_DIR = Path("/root/.openclaw/workspace/.archival")

DEFAULT_CONFIG = {
    # === PRIMARY 信号阈值（模型体感）===
    "failure_rate_threshold": 0.3,   # 检索失败率 > 30% → 触发
    "latency_threshold_ratio": 1.5,  # 当前延迟 > 基准 1.5x → 触发
    
    # === SECONDARY 信号阈值（容量预警）===
    "context_limit_pct": 70,         # 上下文 > 70% → 确认信号
    
    # === 辅助计算 ===
    "baseline_latency_ms": 200.0,    # 初始基准延迟（ms）
    "window_size": 20,               # 滑动窗口大小
    
    # === 操作参数 ===
    "max_active_memories": 50,
    "archival_threshold": 0.3,
}

class MemoryItem:
    def __init__(self, id: str, content: str, memory_type: str,
                 importance_score: float = 0.5, recency_score: float = 0.5,
                 access_count: int = 0, created_at: str = None,
                 last_accessed: str = None, tags: List[str] = None):
        self.id = id
        self.content = content
        self.memory_type = memory_type
        self.importance_score = importance_score
        self.recency_score = recency_score
        self.access_count = access_count
        self.created_at = created_at or datetime.now().isoformat()
        self.last_accessed = last_accessed or datetime.now().isoformat()
        self.tags = tags or []
    
    @property
    def composite_score(self) -> float:
        access_freq = min(1.0, self.access_count / 10)
        return self.importance_score * 0.6 + self.recency_score * 0.3 + access_freq * 0.1
    
    def to_dict(self) -> dict:
        return {
            "id": self.id, "content": self.content,
            "memory_type": self.memory_type,
            "importance_score": self.importance_score,
            "recency_score": self.recency_score,
            "access_count": self.access_count,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "tags": self.tags,
            "composite_score": self.composite_score
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> 'MemoryItem':
        return cls(
            id=d["id"], content=d["content"], memory_type=d["memory_type"],
            importance_score=d.get("importance_score", 0.5),
            recency_score=d.get("recency_score", 0.5),
            access_count=d.get("access_count", 0),
            created_at=d.get("created_at"), last_accessed=d.get("last_accessed"),
            tags=d.get("tags", [])
        )
    
    def update_recency(self):
        days_ago = (datetime.now() - datetime.fromisoformat(self.last_accessed)).days
        self.recency_score = max(0, 1.0 - (days_ago / 30))
        self.last_accessed = datetime.now().isoformat()
    
    def touch(self):
        self.update_recency()
        self.access_count = min(100, self.access_count + 1)


class RetrievalMetrics:
    """
    检索指标追踪器
    
    核心指标：
    - retrieval_miss_rate: 检索失败率（搜索结果为空或质量低）
    - response_latency: 推理延迟（每次检索的响应时间）
    
    这两个指标直接反映"模型体感"——模型自己觉得慢了、找不到东西了
    """
    
    def __init__(self, window_size: int = 20, baseline_latency_ms: float = 200.0):
        self.window_size = window_size
        self.baseline_latency_ms = baseline_latency_ms
        # (success: bool, latency_ms: float)
        # success = False 表示检索"没找到有用的"
        self.history: deque = deque(maxlen=window_size)
    
    def record(self, success: bool, latency_ms: float):
        """记录一次检索"""
        self.history.append((success, latency_ms))
    
    def get_miss_rate(self) -> float:
        """计算检索失败率（miss_rate ↑ 触发换页）"""
        if not self.history:
            return 0.0
        misses = sum(1 for s, _ in self.history if not s)
        return misses / len(self.history)
    
    def get_avg_latency(self) -> float:
        """计算平均延迟"""
        if not self.history:
            return self.baseline_latency_ms
        return sum(l for _, l in self.history) / len(self.history)
    
    def get_latency_ratio(self) -> float:
        """计算延迟倍数（相对于基准）
        
        ratio ↑ 说明模型在变慢 = 记忆碎片化的信号
        """
        return self.get_avg_latency() / self.baseline_latency_ms
    
    def recalibrate(self):
        """
        重新校准基准延迟
        
        正常情况下，平均成功检索的延迟作为新基准
        这能让系统适应"正常变慢"（如模型本身升级）
        """
        successful_latencies = [l for s, l in self.history if s]
        if successful_latencies:
            self.baseline_latency_ms = sum(successful_latencies) / len(successful_latencies)


class MemoryPager:
    """
    记忆分页调度器 - 核心版
    
    双重真实信号驱动（模型体感）：
    
    PRIMARY（直接触发）:
    ┌─────────────────────────────────────┐
    │ retrieval_miss_rate > 30%           │ → 换出
    │ response_latency_ratio > 1.5x       │ → 换出
    └─────────────────────────────────────┘
    
    SECONDARY（确认信号）:
    ┌─────────────────────────────────────┐
    │ context_pressure > 70%               │ → 辅助确认
    └─────────────────────────────────────┘
    
    核心逻辑：
    - PRIMARY 任一触发 → 必须换出
    - SECONDARY 单独触发 → 不一定换出（可能是任务复杂，不是记忆问题）
    - PRIMARY + SECONDARY 同时触发 → 确认是记忆导致的
    """
    
    def __init__(self, config: Dict = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.active_memories: Dict[str, MemoryItem] = {}
        self.archival_memories: Dict[str, MemoryItem] = {}
        self.metrics = RetrievalMetrics(
            window_size=self.config["window_size"],
            baseline_latency_ms=self.config["baseline_latency_ms"]
        )
        self.load()
    
    def _ensure_dirs(self):
        MEMORY_DIR.mkdir(exist_ok=True)
        ARCHIVAL_DIR.mkdir(exist_ok=True)
    
    def load(self):
        self._ensure_dirs()
        try:
            with open(ARCHIVAL_DIR / "active_memories.json") as f:
                self.active_memories = {mid: MemoryItem.from_dict(m) 
                    for mid, m in json.load(f).items()}
        except: pass
        try:
            with open(ARCHIVAL_DIR / "archival_memories.json") as f:
                self.archival_memories = {mid: MemoryItem.from_dict(m) 
                    for mid, m in json.load(f).items()}
        except: pass
        try:
            with open(ARCHIVAL_DIR / "pager_metrics.json") as f:
                d = json.load(f)
                self.metrics.baseline_latency_ms = d.get("baseline_latency_ms", 200.0)
        except: pass
    
    def save(self):
        self._ensure_dirs()
        with open(ARCHIVAL_DIR / "active_memories.json", "w") as f:
            json.dump({mid: m.to_dict() for mid, m in self.active_memories.items()}, f, indent=2)
        with open(ARCHIVAL_DIR / "archival_memories.json", "w") as f:
            json.dump({mid: m.to_dict() for mid, m in self.archival_memories.items()}, f, indent=2)
        with open(ARCHIVAL_DIR / "pager_metrics.json", "w") as f:
            json.dump({"baseline_latency_ms": self.metrics.baseline_latency_ms}, f)
    
    def add(self, content: str, memory_type: str, importance: float = 0.5, 
            tags: List[str] = None) -> str:
        mid = f"mem_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        item = MemoryItem(mid, content, memory_type, importance, recency_score=1.0, tags=tags)
        if item.composite_score < self.config["archival_threshold"]:
            self.archival_memories[mid] = item
        else:
            self.active_memories[mid] = item
        self.save()
        return mid
    
    def search(self, query: str, top_k: int = 5, 
               quality_threshold: float = 0.3) -> List[MemoryItem]:
        """
        搜索记忆，同时记录检索质量
        
        Args:
            query: 搜索查询
            top_k: 返回数量
            quality_threshold: 质量阈值（低于此值的检索算"失败"）
        
        Returns:
            匹配的 MemoryItem 列表
        """
        t0 = time.time()
        query_lower = query.lower()
        results = []
        
        # 在活跃记忆中搜索
        for mid, item in self.active_memories.items():
            if query_lower in item.content.lower():
                item.touch()
                results.append(item)
        
        # 在归档记忆中搜索
        for mid, item in self.archival_memories.items():
            if query_lower in item.content.lower():
                results.append(item)
        
        # 按评分排序
        results.sort(key=lambda x: x.composite_score, reverse=True)
        results = results[:top_k]
        
        # 计算延迟
        latency_ms = (time.time() - t0) * 1000
        
        # 判断成功/失败
        # 失败条件：结果为空 OR 结果质量都很低
        if not results:
            success = False
        else:
            # 最高分如果低于质量阈值，也算失败
            top_score = results[0].composite_score if results else 0.0
            success = top_score >= quality_threshold
        
        # 记录指标
        self.metrics.record(success, latency_ms)
        
        return results
    
    def evaluate_triggers(self, context_pct: float = None) -> Dict:
        """
        评估触发条件
        
        Returns:
            {
                "primary_triggered": bool,
                "primary_type": "miss_rate" | "latency" | None,
                "primary_value": float,
                "secondary_confirmed": bool,
                "context_pct": float,
                "miss_rate": float,
                "latency_ratio": float,
                "verdict": str  # 换出/不换出
            }
        """
        miss_rate = self.metrics.get_miss_rate()
        latency_ratio = self.metrics.get_latency_ratio()
        
        # === PRIMARY 判断 ===
        primary_triggered = False
        primary_type = None
        primary_value = 0.0
        
        if miss_rate >= self.config["failure_rate_threshold"]:
            primary_triggered = True
            primary_type = "miss_rate"
            primary_value = miss_rate
        elif latency_ratio >= self.config["latency_threshold_ratio"]:
            primary_triggered = True
            primary_type = "latency"
            primary_value = latency_ratio
        
        # === SECONDARY 判断 ===
        secondary_confirmed = False
        if context_pct is not None and context_pct >= self.config["context_limit_pct"]:
            secondary_confirmed = True
        
        # === 综合裁决 ===
        if primary_triggered:
            if secondary_confirmed:
                verdict = "EVICT_CONFIRMED"  # PRIMARY + SECONDARY → 确认是记忆问题
            else:
                verdict = "EVICT_PRIMARY"     # PRIMARY only → 相信体感，换出
        else:
            if secondary_confirmed:
                verdict = "MONITOR"  # SECONDARY only → 监控，不立即换出
            else:
                verdict = "OK"      # 无信号 → 正常
        
        return {
            "primary_triggered": primary_triggered,
            "primary_type": primary_type,
            "primary_value": primary_value,
            "secondary_confirmed": secondary_confirmed,
            "context_pct": context_pct,
            "miss_rate": miss_rate,
            "latency_ratio": latency_ratio,
            "verdict": verdict
        }
    
    def decide_and_act(self, context_pct: float = None) -> Dict:
        """
        评估信号并执行操作
        """
        evaluation = self.evaluate_triggers(context_pct)
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "evaluation": evaluation,
            "action": None,
            "evicted": []
        }
        
        verdict = evaluation["verdict"]
        
        if verdict in ("EVICT_CONFIRMED", "EVICT_PRIMARY"):
            # 确定换出数量
            if verdict == "EVICT_CONFIRMED":
                # 双重确认，换出更多
                evict_count = 6
            else:
                # 仅 PRIMARY，换出标准量
                evict_count = 4
            
            evicted = self.page_out(evict_count)
            result["action"] = f"evict_{len(evicted)}"
            result["evicted"] = evicted
        
        elif verdict == "MONITOR":
            result["action"] = "monitor_only"
        
        else:
            result["action"] = "none"
        
        return result
    
    def page_out(self, count: int = 5) -> List[str]:
        """换出最低分记忆"""
        if len(self.active_memories) <= self.config["max_active_memories"]:
            return []
        
        sorted_items = sorted(self.active_memories.items(), 
                             key=lambda x: x[1].composite_score)
        evicted = []
        for mid, item in sorted_items[:count]:
            del self.active_memories[mid]
            self.archival_memories[mid] = item
            evicted.append(mid)
        
        self.save()
        return evicted
    
    def recall(self, query: str, top_k: int = 5) -> List[MemoryItem]:
        """召回相关归档记忆"""
        results = self.search(query, top_k, track_metrics=False)
        recalled = []
        for item in results:
            if item.id in self.archival_memories:
                del self.archival_memories[item.id]
                item.update_recency()
                self.active_memories[item.id] = item
                recalled.append(item)
        self.save()
        return recalled
    
    def recalibrate(self):
        """重新校准基准延迟"""
        self.metrics.recalibrate()
        self.save()
    
    def get_status(self) -> Dict:
        """获取状态"""
        miss_rate = self.metrics.get_miss_rate()
        latency_ratio = self.metrics.get_latency_ratio()
        
        return {
            "active": len(self.active_memories),
            "archival": len(self.archival_memories),
            "primary_signals": {
                "miss_rate": f"{miss_rate:.1%}",
                "latency_ratio": f"{latency_ratio:.2f}x",
                "miss_threshold": f"{self.config['failure_rate_threshold']:.1%}",
                "latency_threshold": f"{self.config['latency_threshold_ratio']:.1f}x"
            },
            "baseline_latency_ms": f"{self.metrics.baseline_latency_ms:.1f}ms",
            "avg_latency_ms": f"{self.metrics.get_avg_latency():.1f}ms"
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Memory Pager - 核心版")
    parser.add_argument("--status", "-s", action="store_true", help="显示状态")
    parser.add_argument("--check", "-c", type=float, metavar="PCT", 
                        help="评估触发信号（传入上下文压力）")
    parser.add_argument("--search", "-q", metavar="QUERY", help="搜索并记录指标")
    parser.add_argument("--evict", "-e", type=int, metavar="N", help="强制换出N条")
    parser.add_argument("--recall", "-r", metavar="QUERY", help="召回")
    parser.add_argument("--recalibrate", action="store_true", help="重新校准基准")
    args = parser.parse_args()
    
    pager = MemoryPager()
    
    if args.status:
        s = pager.get_status()
        print("📊 Memory Pager 状态")
        print(f"活跃记忆: {s['active']}, 归档: {s['archival']}")
        print()
        print("🔴 PRIMARY 信号（模型体感）:")
        print(f"   retrieval_miss_rate: {s['primary_signals']['miss_rate']} (阈值: {s['primary_signals']['miss_threshold']})")
        print(f"   response_latency:     {s['primary_signals']['latency_ratio']} (阈值: {s['primary_signals']['latency_threshold']})")
        print()
        print(f"   基准延迟: {s['baseline_latency_ms']}, 当前平均: {s['avg_latency_ms']}")
    
    elif args.check is not None:
        result = pager.decide_and_act(args.check)
        ev = result["evaluation"]
        
        print(f"🔍 评估结果 (context={args.check}%)")
        print()
        
        # PRIMARY
        primary_fired = "🔴" if ev["primary_triggered"] else "🟢"
        if ev["primary_type"] == "miss_rate":
            print(f"{primary_fired} retrieval_miss_rate: {ev['miss_rate']:.1%}")
        elif ev["primary_type"] == "latency":
            print(f"{primary_fired} response_latency: {ev['latency_ratio']:.2f}x")
        else:
            print(f"🟢 PRIMARY: 无触发")
        
        # SECONDARY
        sec_fired = "🟡" if ev["secondary_confirmed"] else "🟢"
        print(f"{sec_fired} context_pressure: {ev['context_pct']}%")
        
        print()
        print(f"📋 裁决: {ev['verdict']}")
        if result['action']:
            print(f"📦 操作: {result['action']}")
            if result['evicted']:
                print(f"   换出: {result['evicted']}")
    
    elif args.search:
        results = pager.search(args.search)
        print(f"🔍 搜索: {args.search}")
        print(f"   找到: {len(results)} 条")
        for item in results[:5]:
            print(f"   - [{item.composite_score:.2f}] {item.content[:50]}")
    
    elif args.evict:
        evicted = pager.page_out(args.evict)
        print(f"🔄 换出 {len(evicted)} 条")
    
    elif args.recall:
        recalled = pager.recall(args.recall)
        print(f"📥 召回 {len(recalled)} 条")
    
    elif args.recalibrate:
        pager.recalibrate()
        print("✅ 基准延迟已重新校准")


if __name__ == "__main__":
    main()
