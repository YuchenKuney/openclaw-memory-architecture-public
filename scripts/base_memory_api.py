#!/usr/bin/env python3
"""
Base Memory API - 统一记忆操作接口

参考 LangChain Memory 的 BaseMemory 设计

抽象基类，支持多种存储后端：
- MemoryStore (内存)
- FileMemoryStore (文件系统)
- (可扩展) PostgresMemoryStore
- (可扩展) QdrantMemoryStore
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any
from enum import Enum
import json

class MemoryType(Enum):
    """记忆类型"""
    OBSERVATION = "observation"     # 观察记录
    PREFERENCE = "preference"       # 用户偏好
    BEHAVIOR = "behavior"          # 行为规律
    ERROR = "error"                 # 错误教训
    TREND = "trend"                 # 趋势观察
    RULE = "rule"                   # 规则/规范

@dataclass
class MemoryRecord:
    """
    统一的记忆记录数据结构
    
    字段说明：
    - id: 全局唯一标识
    - content: 记忆内容
    - type: 记忆类型
    - importance: 重要性评分 0.0~1.0
    - recency: 新鲜度评分 0.0~1.0
    - created_at: 创建时间
    - updated_at: 更新时间
    - access_count: 访问次数
    - tags: 标签列表
    - metadata: 额外元数据
    """
    id: str
    content: str
    type: MemoryType = MemoryType.OBSERVATION
    importance: float = 0.5
    recency: float = 1.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    access_count: int = 0
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def composite_score(self) -> float:
        """综合评分 = importance * 0.6 + recency * 0.3 + access_freq * 0.1"""
        access_freq = min(1.0, self.access_count / 10)
        return self.importance * 0.6 + self.recency * 0.3 + access_freq * 0.1
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "type": self.type.value,
            "importance": self.importance,
            "recency": self.recency,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "access_count": self.access_count,
            "tags": self.tags,
            "metadata": self.metadata,
            "composite_score": self.composite_score
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> 'MemoryRecord':
        return cls(
            id=d["id"],
            content=d["content"],
            type=MemoryType(d.get("type", "observation")),
            importance=d.get("importance", 0.5),
            recency=d.get("recency", 1.0),
            created_at=d.get("created_at"),
            updated_at=d.get("updated_at"),
            access_count=d.get("access_count", 0),
            tags=d.get("tags", []),
            metadata=d.get("metadata", {})
        )
    
    def update_recency(self):
        """更新新鲜度"""
        days_ago = (datetime.now() - datetime.fromisoformat(self.updated_at)).days
        self.recency = max(0, 1.0 - (days_ago / 30))
        self.updated_at = datetime.now().isoformat()
    
    def touch(self):
        """访问时调用"""
        self.update_recency()
        self.access_count = min(100, self.access_count + 1)


class BaseMemoryStore(ABC):
    """
    记忆存储抽象基类
    
    定义统一的存储接口，各后端实现类只需实现这些方法：
    - add(): 添加记忆
    - get(): 获取单条记忆
    - search(): 搜索记忆
    - update(): 更新记忆
    - delete(): 删除记忆
    - cleanup(): 清理记忆
    """
    
    @abstractmethod
    def add(self, record: MemoryRecord) -> str:
        """添加记忆，返回记忆ID"""
        pass
    
    @abstractmethod
    def get(self, id: str) -> Optional[MemoryRecord]:
        """根据ID获取记忆"""
        pass
    
    @abstractmethod
    def search(self, query: str, top_k: int = 10, filters: Dict = None) -> List[MemoryRecord]:
        """
        搜索记忆
        
        Args:
            query: 搜索查询
            top_k: 返回前k条
            filters: 过滤条件（如 type, tags, importance_min 等）
        """
        pass
    
    @abstractmethod
    def update(self, id: str, updates: Dict) -> bool:
        """更新记忆，返回是否成功"""
        pass
    
    @abstractmethod
    def delete(self, id: str) -> bool:
        """删除记忆，返回是否成功"""
        pass
    
    @abstractmethod
    def list_all(self, filters: Dict = None) -> List[MemoryRecord]:
        """列出所有记忆，可选过滤"""
        pass
    
    @abstractmethod
    def cleanup(self, criteria: Dict) -> int:
        """
        清理记忆
        
        Args:
            criteria: 清理条件（如 max_count, min_score, older_than_days 等）
        Returns:
            清理的记忆数量
        """
        pass
    
    @abstractmethod
    def count(self) -> int:
        """返回记忆总数"""
        pass
    
    def batch_add(self, records: List[MemoryRecord]) -> List[str]:
        """批量添加，返回添加的ID列表"""
        ids = []
        for record in records:
            try:
                mid = self.add(record)
                ids.append(mid)
            except:
                pass
        return ids
    
    def get_by_type(self, memory_type: MemoryType) -> List[MemoryRecord]:
        """按类型获取记忆"""
        return self.list_all(filters={"type": memory_type.value})
    
    def get_top_scores(self, top_k: int = 10) -> List[MemoryRecord]:
        """获取评分最高的记忆"""
        all_records = self.list_all()
        sorted_records = sorted(all_records, key=lambda r: r.composite_score, reverse=True)
        return sorted_records[:top_k]


class FileMemoryStore(BaseMemoryStore):
    """
    基于文件的记忆存储实现
    
    适用于单机环境，数据存储在 JSON 文件中
    """
    
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self._storage_file = f"{storage_path}/memories.json"
        self._index_file = f"{storage_path}/memories_index.json"
        self._memories: Dict[str, MemoryRecord] = {}
        self._load()
    
    def _load(self):
        """从文件加载"""
        import os
        os.makedirs(self.storage_path, exist_ok=True)
        try:
            with open(self._storage_file) as f:
                data = json.load(f)
                self._memories = {mid: MemoryRecord.from_dict(m) for mid, m in data.items()}
        except FileNotFoundError:
            self._memories = {}
    
    def _save(self):
        """保存到文件"""
        with open(self._storage_file, "w") as f:
            json.dump({mid: m.to_dict() for mid, m in self._memories.items()}, f, indent=2, ensure_ascii=False)
    
    def add(self, record: MemoryRecord) -> str:
        self._memories[record.id] = record
        self._save()
        return record.id
    
    def get(self, id: str) -> Optional[MemoryRecord]:
        return self._memories.get(id)
    
    def search(self, query: str, top_k: int = 10, filters: Dict = None) -> List[MemoryRecord]:
        query_lower = query.lower()
        results = []
        
        for record in self._memories.values():
            # 应用过滤器
            if filters:
                if "type" in filters and record.type.value != filters["type"]:
                    continue
                if "importance_min" in filters and record.importance < filters["importance_min"]:
                    continue
                if "tags" in filters and not any(tag in record.tags for tag in filters["tags"]):
                    continue
            
            # 关键词匹配
            if query_lower in record.content.lower():
                results.append(record)
        
        # 按评分排序
        results.sort(key=lambda r: r.composite_score, reverse=True)
        return results[:top_k]
    
    def update(self, id: str, updates: Dict) -> bool:
        record = self._memories.get(id)
        if not record:
            return False
        
        if "content" in updates:
            record.content = updates["content"]
        if "importance" in updates:
            record.importance = updates["importance"]
        if "tags" in updates:
            record.tags = updates["tags"]
        if "metadata" in updates:
            record.metadata = updates["metadata"]
        
        record.updated_at = datetime.now().isoformat()
        self._save()
        return True
    
    def delete(self, id: str) -> bool:
        if id in self._memories:
            del self._memories[id]
            self._save()
            return True
        return False
    
    def list_all(self, filters: Dict = None) -> List[MemoryRecord]:
        results = list(self._memories.values())
        
        if filters:
            results = self._apply_filters(results, filters)
        
        return results
    
    def _apply_filters(self, records: List[MemoryRecord], filters: Dict) -> List[MemoryRecord]:
        """应用过滤条件"""
        filtered = []
        for r in records:
            if "type" in filters and r.type.value != filters["type"]:
                continue
            if "importance_min" in filters and r.importance < filters["importance_min"]:
                continue
            if "tags" in filters and not any(tag in r.tags for tag in filters["tags"]):
                continue
            if "older_than_days" in filters:
                days_ago = (datetime.now() - datetime.fromisoformat(r.created_at)).days
                if days_ago < filters["older_than_days"]:
                    continue
            filtered.append(r)
        return filtered
    
    def cleanup(self, criteria: Dict) -> int:
        """清理记忆"""
        all_records = list(self._memories.values())
        filtered = self._apply_filters(all_records, criteria)
        
        count = 0
        for record in filtered:
            if self.delete(record.id):
                count += 1
        
        return count
    
    def count(self) -> int:
        return len(self._memories)


# 使用示例
def example_usage():
    """使用示例"""
    # 创建存储
    store = FileMemoryStore("/root/.openclaw/workspace/.memory_store")
    
    # 添加记忆
    record = MemoryRecord(
        id="mem_001",
        content="坤哥喜欢简洁直接的回复",
        type=MemoryType.PREFERENCE,
        importance=0.8,
        tags=["偏好", "沟通"]
    )
    store.add(record)
    
    # 搜索
    results = store.search("坤哥")
    for r in results:
        print(f"[{r.type.value}] {r.content}")
    
    # 清理（删除评分低于0.3的旧记忆）
    deleted = store.cleanup({"importance_min": 0.3, "older_than_days": 90})
    print(f"清理了 {deleted} 条记忆")


if __name__ == "__main__":
    example_usage()
