#!/usr/bin/env python3
"""
Memory System - 可插拔记忆系统

核心设计：
1. MemoryItem - 统一的记忆数据结构
2. MemoryManager - 唯一入口，所有模块只能调用它
3. Backend Adapter - 可插拔存储后端
   ├── FileMemory
   ├── VectorDBMemory (Qdrant)
   └── GraphMemory (Neo4j)

关键方法：
- add()        - 添加记忆
- search()     - 检索记忆
- update()     - 更新记忆
- decay()      - 重要性衰减
- resolve_conflict() - 矛盾解决
"""

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path
from collections import deque

# ============ MemoryItem ============

@dataclass
class MemoryItem:
    """
    统一的记忆数据结构
    
    所有字段：
    - id: 全局唯一标识
    - content: 记忆内容
    - type: 记忆类型（observation/preference/behavior/error/trend/rule）
    - timestamp: 创建时间（ISO格式）
    - importance: 重要性评分（0.0~1.0）
    - recency: 新鲜度评分（0.0~1.0）
    - embedding: 向量嵌入（可选，用于向量检索）
    - relations: 关系列表（用于知识图谱）
    """
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
    
    @property
    def composite_score(self) -> float:
        """综合评分 = importance×0.6 + recency×0.3 + access_freq×0.1"""
        access_freq = min(1.0, self.access_count / 10)
        return self.importance * 0.6 + self.recency * 0.3 + access_freq * 0.1
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d["composite_score"] = self.composite_score
        return d
    
    @classmethod
    def from_dict(cls, d: dict) -> 'MemoryItem':
        # 兼容旧格式
        d.pop("composite_score", None)
        return cls(**d)
    
    def touch(self):
        """访问时调用：更新新鲜度 + 增加访问次数"""
        self.access_count = min(100, self.access_count + 1)
        self.last_accessed = datetime.now().isoformat()
        self.update_recency()
    
    def update_recency(self):
        """更新新鲜度"""
        last = datetime.fromisoformat(self.last_accessed)
        days_ago = (datetime.now() - last).days
        self.recency = max(0, 1.0 - (days_ago / 30))


# ============ BaseMemoryBackend ============

class BaseMemoryBackend(ABC):
    """
    记忆存储后端抽象基类
    
    所有后端必须实现：
    - add()
    - get()
    - search()
    - update()
    - delete()
    - list_all()
    - cleanup()
    """
    
    @abstractmethod
    def add(self, item: MemoryItem) -> str:
        """添加记忆，返回ID"""
        pass
    
    @abstractmethod
    def get(self, id: str) -> Optional[MemoryItem]:
        """根据ID获取"""
        pass
    
    @abstractmethod
    def search(self, query: str, top_k: int = 10) -> List[MemoryItem]:
        """搜索记忆"""
        pass
    
    @abstractmethod
    def update(self, id: str, updates: Dict) -> bool:
        """更新记忆"""
        pass
    
    @abstractmethod
    def delete(self, id: str) -> bool:
        """删除记忆"""
        pass
    
    @abstractmethod
    def list_all(self) -> List[MemoryItem]:
        """列出所有记忆"""
        pass
    
    @abstractmethod
    def cleanup(self, criteria: Dict) -> int:
        """清理记忆，返回清理数量"""
        pass


# ============ FileMemory Backend ============

class FileMemory(BaseMemoryBackend):
    """
    文件系统后端（单机适用）
    """
    
    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.storage_file = self.storage_path / "memories.json"
        self._memories: Dict[str, MemoryItem] = {}
        self._load()
    
    def _load(self):
        self.storage_path.mkdir(parents=True, exist_ok=True)
        if self.storage_file.exists():
            with open(self.storage_file) as f:
                data = json.load(f)
                self._memories = {mid: MemoryItem.from_dict(m) for mid, m in data.items()}
    
    def _save(self):
        with open(self.storage_file, "w") as f:
            json.dump({mid: m.to_dict() for mid, m in self._memories.items()}, f, indent=2, ensure_ascii=False)
    
    def add(self, item: MemoryItem) -> str:
        self._memories[item.id] = item
        self._save()
        return item.id
    
    def get(self, id: str) -> Optional[MemoryItem]:
        return self._memories.get(id)
    
    def search(self, query: str, top_k: int = 10) -> List[MemoryItem]:
        query_lower = query.lower()
        results = [
            m for m in self._memories.values()
            if query_lower in m.content.lower()
        ]
        results.sort(key=lambda x: x.composite_score, reverse=True)
        return results[:top_k]
    
    def update(self, id: str, updates: Dict) -> bool:
        item = self._memories.get(id)
        if not item:
            return False
        for key, value in updates.items():
            if hasattr(item, key):
                setattr(item, key, value)
        self._save()
        return True
    
    def delete(self, id: str) -> bool:
        if id in self._memories:
            del self._memories[id]
            self._save()
            return True
        return False
    
    def list_all(self) -> List[MemoryItem]:
        return list(self._memories.values())
    
    def cleanup(self, criteria: Dict) -> int:
        """清理：低于重要性阈值 或 超过30天"""
        to_delete = []
        for item in self._memories.values():
            if item.composite_score < criteria.get("min_score", 0.2):
                to_delete.append(item.id)
            elif item.importance < criteria.get("min_importance", 0.1):
                to_delete.append(item.id)
        
        for mid in to_delete:
            del self._memories[mid]
        self._save()
        return len(to_delete)


# ============ VectorDBMemory Backend (Qdrant) ============

class VectorDBMemory(BaseMemoryBackend):
    """
    向量数据库后端（Qdrant）
    
    需要安装 qdrant-client
    """
    
    def __init__(self, url: str = "localhost:6333", collection: str = "memories"):
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http import models
            self.client = QdrantClient(url=url)
            self.collection = collection
            self._ensure_collection()
        except ImportError:
            raise ImportError("qdrant-client 未安装: pip install qdrant-client")
    
    def _ensure_collection(self):
        from qdrant_client.http import models
        try:
            self.client.get_collection(self.collection)
        except:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
            )
    
    def add(self, item: MemoryItem) -> str:
        payload = item.to_dict()
        payload.pop("embedding", None)  # 不重复存储
        self.client.upsert(
            collection_name=self.collection,
            points=[{
                "id": item.id,
                "vector": item.embedding or self._generate_dummy_vector(),
                "payload": payload
            }]
        )
        return item.id
    
    def _generate_dummy_vector(self) -> List[float]:
        """生成假向量（实际应调用 embedding 模型）"""
        import hashlib
        h = int(hashlib.md5(self._memories[item.id].content.encode()).hexdigest()[:8], 16)
        import random
        random.seed(h)
        return [random.random() for _ in range(384)]
    
    def get(self, id: str) -> Optional[MemoryItem]:
        results = self.client.retrieve(collection_name=self.collection, ids=[id])
        if results:
            return MemoryItem.from_dict(results[0].payload)
        return None
    
    def search(self, query: str, top_k: int = 10) -> List[MemoryItem]:
        # 简化：先用关键词过滤，实际应该用向量相似度
        # 这里需要 embedding 模型来生成查询向量
        results = self.client.scroll(collection_name=self.collection, limit=100)[0]
        items = [MemoryItem.from_dict(r.payload) for r in results]
        query_lower = query.lower()
        filtered = [m for m in items if query_lower in m.content.lower()]
        filtered.sort(key=lambda x: x.composite_score, reverse=True)
        return filtered[:top_k]
    
    def update(self, id: str, updates: Dict) -> bool:
        item = self.get(id)
        if not item:
            return False
        for key, value in updates.items():
            if hasattr(item, key):
                setattr(item, key, value)
        self.client.upsert(collection_name=self.collection, points=[{
            "id": id,
            "vector": item.embedding or [0.0]*384,
            "payload": item.to_dict()
        }])
        return True
    
    def delete(self, id: str) -> bool:
        self.client.delete(collection_name=self.collection, points=[id])
        return True
    
    def list_all(self) -> List[MemoryItem]:
        results = self.client.scroll(collection_name=self.collection, limit=1000)[0]
        return [MemoryItem.from_dict(r.payload) for r in results]
    
    def cleanup(self, criteria: Dict) -> int:
        count = 0
        for item in self.list_all():
            if item.composite_score < criteria.get("min_score", 0.2):
                self.delete(item.id)
                count += 1
        return count


# ============ GraphMemory Backend (Neo4j) ============

class GraphMemory(BaseMemoryBackend):
    """
    知识图谱后端（Neo4j）
    
    需要安装 neo4j
    """
    
    def __init__(self, uri: str = "bolt://localhost:7687", 
                 user: str = "neo4j", password: str = "password"):
        try:
            from neo4j import GraphDatabase
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
        except ImportError:
            raise ImportError("neo4j 未安装: pip install neo4j")
    
    def close(self):
        self.driver.close()
    
    def add(self, item: MemoryItem) -> str:
        with self.driver.session() as session:
            session.run("""
                MERGE (m:Memory {id: $id})
                SET m.content = $content,
                    m.type = $type,
                    m.timestamp = $timestamp,
                    m.importance = $importance,
                    m.recency = $recency,
                    m.tags = $tags
            """, **item.to_dict())
        return item.id
    
    def get(self, id: str) -> Optional[MemoryItem]:
        with self.driver.session() as session:
            result = session.run("MATCH (m:Memory {id: $id}) RETURN m", id=id)
            record = result.single()
            if record:
                return MemoryItem.from_dict(record["m"])
        return None
    
    def search(self, query: str, top_k: int = 10) -> List[MemoryItem]:
        with self.driver.session() as session:
            result = session.run("""
                MATCH (m:Memory)
                WHERE m.content CONTAINS $query
                RETURN m
                ORDER BY m.importance DESC
                LIMIT $limit
            """, query=query, limit=top_k)
            return [MemoryItem.from_dict(record["m"]) for record in result]
    
    def update(self, id: str, updates: Dict) -> bool:
        with self.driver.session() as session:
            result = session.run("MATCH (m:Memory {id: $id}) RETURN m", id=id)
            if not result.single():
                return False
            set_clause = ", ".join([f"m.{k} = ${k}" for k in updates.keys()])
            session.run(f"MATCH (m:Memory {{id: $id}}) SET {set_clause}", id=id, **updates)
        return True
    
    def delete(self, id: str) -> bool:
        with self.driver.session() as session:
            result = session.run("MATCH (m:Memory {id: $id}) DELETE m", id=id)
            return result.consumedounters().nodes_deleted > 0
    
    def list_all(self) -> List[MemoryItem]:
        with self.driver.session() as session:
            result = session.run("MATCH (m:Memory) RETURN m")
            return [MemoryItem.from_dict(record["m"]) for record in result]
    
    def cleanup(self, criteria: Dict) -> int:
        with self.driver.session() as session:
            result = session.run("""
                MATCH (m:Memory)
                WHERE m.importance < $min_imp
                DELETE m
                RETURN count(*) as c
            """, min_imp=criteria.get("min_importance", 0.1))
            return result.single()["c"]


# ============ MemoryManager (唯一入口) ============

class MemoryManager:
    """
    记忆管理器 - 唯一入口
    
    所有模块只能调用这个类，不能直接操作后端
    
    核心方法：
    - add()
    - search()
    - update()
    - decay()
    - resolve_conflict()
    """
    
    def __init__(self, backend: BaseMemoryBackend):
        self.backend = backend
        self._decay_enabled = True
        self._decay_factor = 0.95  # 每次 decay 重要性乘以这个
    
    def add(self, content: str, type: str = "observation",
            importance: float = 0.5, tags: List[str] = None,
            relations: List[Dict] = None, id: str = None) -> str:
        """
        添加记忆
        """
        mid = id or f"mem_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        item = MemoryItem(
            id=mid,
            content=content,
            type=type,
            importance=importance,
            tags=tags or [],
            relations=relations or []
        )
        return self.backend.add(item)
    
    def get(self, id: str) -> Optional[MemoryItem]:
        return self.backend.get(id)
    
    def search(self, query: str, top_k: int = 10) -> List[MemoryItem]:
        """
        搜索记忆（同时更新访问指标）
        """
        results = self.backend.search(query, top_k)
        for item in results:
            item.touch()
        return results
    
    def update(self, id: str, **kwargs) -> bool:
        """
        更新记忆
        """
        return self.backend.update(id, kwargs)
    
    def delete(self, id: str) -> bool:
        return self.backend.delete(id)
    
    def decay(self) -> Dict:
        """
        重要性衰减
        
        定期调用，让所有记忆的重要性随时间缓慢衰减
        低于阈值的记忆会被归档或删除
        """
        if not self._decay_enabled:
            return {"status": "disabled", "decayed": 0}
        
        all_items = self.backend.list_all()
        decayed = 0
        archived = []
        
        for item in all_items:
            old_score = item.composite_score
            item.importance *= self._decay_factor
            item.recency = max(0, item.recency - 0.05)
            decayed += 1
        
        # 清理低于阈值
        cleaned = self.backend.cleanup({"min_score": 0.1, "min_importance": 0.05})
        
        return {
            "status": "ok",
            "decayed": decayed,
            "cleaned": cleaned
        }
    
    def resolve_conflict(self, id1: str, id2: str, strategy: str = "auto") -> Dict:
        """
        解决记忆矛盾
        
        策略：
        - "auto": 置信度高的保留
        - "merge": 合并两者内容
        - "user": 标记待用户裁决
        """
        item1 = self.backend.get(id1)
        item2 = self.backend.get(id2)
        
        if not item1 or not item2:
            return {"status": "error", "message": "记忆不存在"}
        
        if strategy == "auto":
            # 保留综合评分高的
            winner = item1 if item1.composite_score >= item2.composite_score else item2
            loser = item2 if item1.composite_score >= item2.composite_score else item1
            self.backend.delete(loser.id)
            return {
                "status": "resolved",
                "winner": winner.id,
                "loser": loser.id,
                "strategy": "auto"
            }
        
        elif strategy == "merge":
            # 合并内容（保留两个，但内容合并）
            merged_content = f"{item1.content}\n---\n{item2.content}"
            item1.content = merged_content
            item1.importance = max(item1.importance, item2.importance)
            item1.tags = list(set(item1.tags + item2.tags))
            self.backend.update(item1.id, item1.to_dict())
            self.backend.delete(item2.id)
            return {
                "status": "merged",
                "kept": item1.id,
                "deleted": item2.id,
                "strategy": "merge"
            }
        
        else:
            # 标记待裁决
            item1.tags = item1.tags + ["conflict_pending"]
            item2.tags = item2.tags + ["conflict_pending"]
            self.backend.update(item1.id, {"tags": item1.tags})
            self.backend.update(item2.id, {"tags": item2.tags})
            return {
                "status": "pending_user",
                "item1": id1,
                "item2": id2,
                "strategy": "user"
            }
    
    def get_stats(self) -> Dict:
        """获取记忆统计"""
        all_items = self.backend.list_all()
        by_type = {}
        for item in all_items:
            by_type[item.type] = by_type.get(item.type, 0) + 1
        
        return {
            "total": len(all_items),
            "by_type": by_type,
            "backend": self.backend.__class__.__name__
        }


# ============ 使用示例 ============

def example():
    """使用示例"""
    # 选择后端
    backend = FileMemory("/tmp/memory_test")
    manager = MemoryManager(backend)
    
    # 添加记忆
    id1 = manager.add("坤哥喜欢简洁直接的回复", type="preference", importance=0.8)
    id2 = manager.add("服务器IP是 154.64.253.249", type="observation", importance=0.6)
    print(f"添加: {id1}, {id2}")
    
    # 搜索
    results = manager.search("坤哥")
    print(f"搜索结果: {len(results)} 条")
    
    # 统计
    stats = manager.get_stats()
    print(f"统计: {stats}")
    
    # 衰减
    decay_result = manager.decay()
    print(f"衰减: {decay_result}")


if __name__ == "__main__":
    example()
