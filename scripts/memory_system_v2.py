#!/usr/bin/env python3
"""
Memory System v2 - 记忆主权(Memory Ownership)

核心理念:MemoryManager 是唯一入口,所有写入必须经过它

迭代步骤:
1. ✅ 接管 Memory 写入(当前)
2. OpenClaw 原生 memory 变成 Backend
3. 所有模块走 MemoryManager

当前 v2 架构:
```
所有记忆写入
    ↓
MemoryManager.add()
    ↓
┌─────────────────────────────────────┐
│ 1. 类型判断(重要/经验/关系/检索)        │
│ 2. 目标选择:                          │
│    - 重要长期 → MEMORY.md              │
│    - 经验行为 → Topic Files            │
│    - 实体关系 → Knowledge Graph         │
│    - 向量检索 → VectorDB              │
│ 3. 一致性写入(多目标原子操作)           │
└─────────────────────────────────────┘
```

问题修复:
- ❌ "双 memory 系统冲突" → ✅ 统一入口
- ❌ 不知道用哪套 memory → ✅ 只有 MemoryManager
- ❌ 写入路径不统一 → ✅ 强制路由
"""

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path
from enum import Enum

# ============ MemoryType(记忆类型枚举)============

class MemoryType(Enum):
    """记忆类型,决定写入目标"""
    CORE = "core"           # 核心长期 → MEMORY.md
    OBSERVATION = "observation"  # 日常观察 → daily logs
    PREFERENCE = "preference"  # 用户偏好 → Topic Files
    BEHAVIOR = "behavior"    # 行为规律 → Topic Files
    ERROR = "error"         # 错误教训 → shared/errors/
    ENTITY = "entity"        # 实体 → Knowledge Graph
    RULE = "rule"            # 规则 → shared/rules/
    TRANSACTIONAL = "transactional"  # 事务性 → daily logs(不沉淀)


# ============ MemoryItem(统一数据结构)============

@dataclass
class MemoryItem:
    """统一记忆数据结构"""
    id: str
    content: str
    type: str = "observation"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    importance: float = 0.5
    recency: float = 1.0
    embedding: Optional[List[float]] = None
    relations: List[Dict] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    access_count: int = 0
    last_accessed: str = field(default_factory=lambda: datetime.now().isoformat())
    source: str = "unknown"  # 来源:user_input / auto_generated / extracted / imported

    @property
    def composite_score(self) -> float:
        access_freq = min(1.0, self.access_count / 10)
        return self.importance * 0.6 + self.recency * 0.3 + access_freq * 0.1

    def to_dict(self) -> dict:
        d = asdict(self)
        d["composite_score"] = self.composite_score
        return d

    @classmethod
    def from_dict(cls, d: dict) -> 'MemoryItem':
        d.pop("composite_score", None)
        return cls(**d)

    def touch(self):
        self.access_count = min(100, self.access_count + 1)
        self.last_accessed = datetime.now().isoformat()
        days_ago = (datetime.now() - datetime.fromisoformat(self.last_accessed)).days
        self.recency = max(0, 1.0 - (days_ago / 30))


# ============ 写入目标路由表 ============

MEMORY_TARGETS = {
    # 类型 → 目标路径
    "core": ["memory.md"],
    "observation": ["daily_log"],
    "preference": ["topic_files"],
    "behavior": ["topic_files"],
    "error": ["shared/errors", "memory.md"],
    "entity": ["knowledge_graph", "topic_files"],
    "rule": ["shared/rules", "memory.md"],
    "transactional": [],  # 只记录,不沉淀
}


# ============ BaseMemoryBackend ============

class BaseMemoryBackend(ABC):
    """后端抽象基类"""

    @abstractmethod
    def add(self, item: MemoryItem) -> str: pass

    @abstractmethod
    def get(self, id: str) -> Optional[MemoryItem]: pass

    @abstractmethod
    def search(self, query: str, top_k: int = 10, filters: Dict = None) -> List[MemoryItem]: pass

    @abstractmethod
    def update(self, id: str, updates: Dict) -> bool: pass

    @abstractmethod
    def delete(self, id: str) -> bool: pass

    @abstractmethod
    def list_all(self, filters: Dict = None) -> List[MemoryItem]: pass


# ============ OpenClawNativeBackend(原生 Memory 适配)============

class OpenClawNativeBackend(BaseMemoryBackend):
    """
    OpenClaw 原生 Memory 后端适配器

    将 OpenClaw 的文件结构映射为 Backend:
    - MEMORY.md → core memory
    - memory/YYYY-MM-DD.md → daily logs
    - shared/* → topic files
    - entities.json → knowledge graph
    """

    def __init__(self, workspace_path: str = "/root/.openclaw/workspace"):
        self.workspace = Path(workspace_path)
        self.memory_file = self.workspace / "MEMORY.md"
        self.daily_dir = self.workspace / "memory"
        self.shared_dir = self.workspace / "shared"

        self._memory_cache: Dict[str, MemoryItem] = {}
        self._load_core_memory()

    def _load_core_memory(self):
        """加载 MEMORY.md 为 MemoryItem"""
        if self.memory_file.exists():
            content = self.memory_file.read_text()
            # 解析 MEMORY.md 结构
            lines = content.split("\n")
            for line in lines:
                if line.strip().startswith("- "):
                    # 简单解析
                    text = line.strip()[2:]
                    mid = f"core_{hash(text) % 100000}"
                    self._memory_cache[mid] = MemoryItem(
                        id=mid,
                        content=text,
                        type="core",
                        importance=0.8,  # core 类型默认高重要性
                        source="native"
                    )

    def _save_core_memory(self):
        """保存 MemoryItem 回 MEMORY.md"""
        lines = ["# MEMORY.md - 长期记忆\n\n"]
        for item in self._memory_cache.values():
            if item.type == "core":
                lines.append(f"- {item.content}\n")
        self.memory_file.write_text("\n".join(lines))

    def add(self, item: MemoryItem) -> str:
        """写入记忆（根据类型路由）"""
        # 1. 先写入 cache（保证 get/search 能拿到）
        self._memory_cache[item.id] = item

        # 2. 再路由到目标文件
        targets = MEMORY_TARGETS.get(item.type, [])

        if "memory.md" in targets or item.type == "core":
            self._save_core_memory()

        if "daily_log" in targets:
            self._write_daily_log(item)

        if "topic_files" in targets:
            self._write_topic_file(item)

        if "shared/errors" in targets and item.type == "error":
            self._write_shared_error(item)

        if "knowledge_graph" in targets or item.type == "entity":
            self._write_entity(item)

        return item.id

    def _write_daily_log(self, item: MemoryItem):
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.daily_dir / f"{today}.md"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        existing = log_file.read_text() if log_file.exists() else ""
        new_entry = f"\n## {item.timestamp}\n- {item.content}\n"
        log_file.write_text(existing + new_entry)

    def _write_topic_file(self, item: MemoryItem):
        topic_file = self.shared_dir / f"{item.type}s.md"
        topic_file.parent.mkdir(parents=True, exist_ok=True)

        existing = topic_file.read_text() if topic_file.exists() else ""
        new_entry = f"\n- [{item.id}] {item.content}\n"
        topic_file.write_text(existing + new_entry)

    def _write_shared_error(self, item: MemoryItem):
        error_file = self.shared_dir / "errors" / f"{item.id}.md"
        error_file.parent.mkdir(parents=True, exist_ok=True)
        error_file.write_text(f"# Error: {item.id}\n\n{item.content}\n")

    def _write_entity(self, item: MemoryItem):
        entity_file = self.workspace / ".entities.json"

        entities = {}
        if entity_file.exists():
            entities = json.loads(entity_file.read_text())

        entities[item.id] = {
            "content": item.content,
            "relations": item.relations,
            "timestamp": item.timestamp
        }

        entity_file.write_text(json.dumps(entities, indent=2, ensure_ascii=False))

    def get(self, id: str) -> Optional[MemoryItem]:
        return self._memory_cache.get(id)

    def search(self, query: str, top_k: int = 10, filters: Dict = None) -> List[MemoryItem]:
        query_lower = query.lower()
        results = []
        seen_content: set = set()  # 去重：按内容hash（去首尾空白）

        # 1. 优先搜 cache（结构化 MemoryItem）
        for item in self._memory_cache.values():
            if query_lower in item.content.lower():
                content_key = item.content.strip()[:60]
                if content_key not in seen_content:
                    seen_content.add(content_key)
                    results.append(item)

        # 2. 搜 daily logs（作为 fallback，只补充 cache 找不到的）
        if self.daily_dir.exists():
            for log_file in sorted(self.daily_dir.glob("2026-*.md"))[-7:]:
                content = log_file.read_text()
                if query_lower in content.lower():
                    # 检查是否和 cache 重复
                    content_key = content.strip()[:60]
                    if content_key not in seen_content:
                        seen_content.add(content_key)
                        results.append(MemoryItem(
                            id=f"log_{log_file.stem}",
                            content=content[:500],
                            type="observation",
                            source="daily_log"
                        ))

        # 3. 搜 topic files（作为补充）
        if self.shared_dir.exists():
            for topic_file in self.shared_dir.glob("*.md"):
                content = topic_file.read_text()
                if query_lower in content.lower():
                    content_key = content.strip()[:60]
                    if content_key not in seen_content:
                        seen_content.add(content_key)
                        results.append(MemoryItem(
                            id=f"topic_{topic_file.stem}",
                            content=content[:200],
                            type="topic",
                            source="topic_files"
                        ))

        results.sort(key=lambda x: x.composite_score, reverse=True)
        return results[:top_k]

    def update(self, id: str, updates: Dict) -> bool:
        if id in self._memory_cache:
            item = self._memory_cache[id]
            for k, v in updates.items():
                if hasattr(item, k):
                    setattr(item, k, v)
            return True
        return False

    def delete(self, id: str) -> bool:
        if id in self._memory_cache:
            del self._memory_cache[id]
            return True
        return False

    def list_all(self, filters: Dict = None) -> List[MemoryItem]:
        results = list(self._memory_cache.values())
        if filters:
            if "type" in filters:
                results = [r for r in results if r.type == filters["type"]]
        return results


# ============ VectorDBBackend(可选后端)============

class VectorDBBackend(BaseMemoryBackend):
    """
    向量数据库后端(可选)

    用于大规模向量检索
    """

    def __init__(self, collection: str = "memories"):
        self.collection = collection
        self._items: Dict[str, MemoryItem] = {}
        # 简化实现,实际需要 Qdrant/Milvus

    def add(self, item: MemoryItem) -> str:
        self._items[item.id] = item
        return item.id

    def get(self, id: str) -> Optional[MemoryItem]:
        return self._items.get(id)

    def search(self, query: str, top_k: int = 10, filters: Dict = None) -> List[MemoryItem]:
        # 简化:关键词搜索
        query_lower = query.lower()
        results = [m for m in self._items.values() if query_lower in m.content.lower()]
        results.sort(key=lambda x: x.composite_score, reverse=True)
        return results[:top_k]

    def update(self, id: str, updates: Dict) -> bool:
        if id in self._items:
            item = self._items[id]
            for k, v in updates.items():
                if hasattr(item, k):
                    setattr(item, k, v)
            return True
        return False

    def delete(self, id: str) -> bool:
        if id in self._items:
            del self._items[id]
            return True
        return False

    def list_all(self, filters: Dict = None) -> List[MemoryItem]:
        return list(self._items.values())


# ============ MemoryManager(唯一入口)============

class MemoryManager:
    """
    记忆管理器 - 唯一入口(Memory Ownership)

    所有记忆写入必须经过这里

    核心职责:
    1. 接收所有写入请求
    2. 判断记忆类型
    3. 路由到正确目标
    4. 保证一致性
    """

    def __init__(self, backends: List[BaseMemoryBackend] = None):
        """
        Args:
            backends: 存储后端列表,默认使用 OpenClawNativeBackend
        """
        self.backends = backends or [OpenClawNativeBackend()]
        self.write_log: List[Dict] = []  # 写入日志,用于调试追踪

    def add(self, content: str, type: str = "observation",
            importance: float = 0.5, tags: List[str] = None,
            relations: List[Dict] = None, source: str = "unknown",
            id: str = None) -> str:
        """
        添加记忆(唯一入口)

        强制经过 MemoryManager,由它决定写入目标
        """
        mid = id or f"mem_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        item = MemoryItem(
            id=mid,
            content=content,
            type=type,
            importance=importance,
            tags=tags or [],
            relations=relations or [],
            source=source
        )

        # 记录写入
        self._log_write("add", item)

        # 写入所有适用后端
        for backend in self.backends:
            try:
                backend.add(item)
            except Exception as e:
                self._log_write("add_error", {"item": item.id, "error": str(e)})

        return mid

    def get(self, id: str) -> Optional[MemoryItem]:
        """从所有后端获取"""
        for backend in self.backends:
            item = backend.get(id)
            if item:
                return item
        return None

    def search(self, query: str, top_k: int = 10,
               type_filter: str = None,
               source_filter: str = None,
               router: str = "auto") -> List[MemoryItem]:
        """
        统一检索入口（接管所有读取）

        内部路由策略（router 参数）：
        - "auto": 所有后端合并
        - "graph": 优先知识图谱 + 向量
        - "recent": 优先最近记忆
        - "keyword": 纯关键词匹配

        替换了原来散落的：
        - graph_query(...)
        - vector_search(...)
        - read_MEMEORY_md(...)
        """
        all_results: Dict[str, MemoryItem] = {}

        for backend in self.backends:
            # 按路由策略选择后端
            backend_name = backend.__class__.__name__

            if router == "graph" and "Vector" not in backend_name and "Graph" not in backend_name:
                continue

            results = backend.search(query, top_k * 2,
                                  filters={"type": type_filter} if type_filter else None)

            for item in results:
                # 来源过滤
                if source_filter and item.source != source_filter:
                    continue
                # 去重（按 id）
                if item.id not in all_results:
                    all_results[item.id] = item

        # 路由策略再排序
        sorted_results = sorted(all_results.values(),
                             key=lambda x: x.composite_score, reverse=True)

        # recent 路由：按时间排序
        if router == "recent":
            sorted_results = sorted(all_results.values(),
                                 key=lambda x: x.timestamp, reverse=True)

        return sorted_results[:top_k]

    def update(self, id: str, **updates) -> bool:
        """更新记忆"""
        for backend in self.backends:
            if backend.update(id, updates):
                self._log_write("update", {"id": id, "updates": updates})
                return True
        return False

    def delete(self, id: str) -> bool:
        """删除记忆"""
        success = False
        for backend in self.backends:
            if backend.delete(id):
                success = True

        if success:
            self._log_write("delete", {"id": id})

        return success

    def _log_write(self, action: str, data: Any):
        """写入操作日志"""
        self.write_log.append({
            "time": datetime.now().isoformat(),
            "action": action,
            "data": data
        })
        # 只保留最近100条
        self.write_log = self.write_log[-100:]

    def get_write_log(self) -> List[Dict]:
        """获取写入日志(用于调试"谁在写入")"""
        return self.write_log

    def get_stats(self) -> Dict:
        """获取记忆统计"""
        total = 0
        by_type: Dict[str, int] = {}

        for backend in self.backends:
            items = backend.list_all()
            total += len(items)
            for item in items:
                by_type[item.type] = by_type.get(item.type, 0) + 1

        return {
            "total": total,
            "by_type": by_type,
            "backends": [b.__class__.__name__ for b in self.backends],
            "write_operations": len(self.write_log)
        }

    def route_type(self, content: str, context: Dict = None) -> str:
        """
        根据内容自动判断类型

        这是一个关键决策点
        """
        content_lower = content.lower()

        # 规则性语句 → core
        if any(kw in content for kw in ["必须", "铁律", "永远不要", "记住"]):
            return "core"

        # 错误/失败 → error
        if any(kw in content_lower for kw in ["错误", "失败", "问题", "bug", "异常"]):
            return "error"

        # 偏好性 → preference
        if any(kw in content for kw in ["喜欢", "不喜欢", "偏好", "要", "不要", "应该", "不应该"]):
            return "preference"

        # 实体/关系 → entity
        if any(kw in content for kw in ["是", "在", "位于", "属于", "的"]):
            if context and context.get("is_entity_reference"):
                return "entity"

        # 默认 → observation
        return "observation"


# ============ 示例用法 ============

def example():
    """使用示例"""
    # 初始化(只用 OpenClawNativeBackend)
    manager = MemoryManager([OpenClawNativeBackend()])

    # ✅ 所有写入必须经过 add()
    manager.add(
        content="坤哥喜欢简洁直接的回复",
        type="preference",
        importance=0.8,
        tags=["偏好", "沟通"],
        source="user_input"
    )

    manager.add(
        content="数据库连接失败,重启后恢复",
        type="error",
        importance=0.7,
        source="system"
    )

    # 检索也必须经过 search()
    results = manager.search("坤哥")
    print(f"找到 {len(results)} 条记忆")

    # 查看写入日志(调试"谁在写入")
    log = manager.get_write_log()
    print(f"写入操作: {len(log)} 条")

    # 统计
    stats = manager.get_stats()
    print(f"记忆统计: {stats}")


if __name__ == "__main__":
    example()
