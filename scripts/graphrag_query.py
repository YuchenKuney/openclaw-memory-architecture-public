#!/usr/bin/env python3
"""
Advanced RAG Query - 高级 RAG 查询引擎（Memory Ownership 版）

核心升级：
  ❌ 旧：各模块自己读文件（graph_query, vector_search, read_MEMORY_md）
  ✅ 新：统一走 MemoryManager.search()——读取也接管了

流程：
  query → decomposition → multi-retrieval → rerank → merge

multi-retrieval 的 retrieve_by_keyword / retrieve_by_graph /
retrieve_by_vector 在有 MemoryManager 时全部走统一入口。
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Optional

GRAPH_FILE = Path("/root/.openclaw/workspace/.knowledge_graph.json")
COMMUNITY_FILE = Path("/root/.openclaw/workspace/.communities.json")


# ============ Query Decomposition ============

class QueryDecomposer:
    """
    查询分解器
    将用户的一个 query 分解为多个子查询
    """

    DECOMPOSITION_PATTERNS = [
        (r"(.+?)(?:和|与)(.+)", 2),
        (r"(.+?)以及(.+)", 2),
        (r"关于(.+?)的(.+)", 2),
    ]

    def decompose(self, query: str) -> List[str]:
        query = query.strip()
        for pattern, groups in self.DECOMPOSITION_PATTERNS:
            matches = re.findall(pattern, query)
            if matches and len(matches[0]) == groups:
                parts = list(matches[0])
                if all(p.strip() for p in parts):
                    return [p.strip() for p in parts]

        connectors = ["的", "在", "和", "与", "及", "还有"]
        parts = [query]
        for conn in connectors:
            new_parts = []
            for part in parts:
                new_parts.extend(part.split(conn))
            if len(new_parts) > len(parts):
                parts = new_parts
                break

        if len(parts) > 1:
            sub = [p.strip() for p in parts if p.strip()]
            if len(sub) > 1 and sub[0] != query:
                return sub
        return [query]

    def identify_intent(self, query: str) -> str:
        q = query.lower()
        if any(kw in q for kw in ["是什么", "哪个", "谁", "多少", "怎么"]):
            return "specific"
        if any(kw in q for kw in ["所有", "总体", "整体", "规律", "趋势", "如何", "怎样"]):
            return "global"
        if any(kw in q for kw in ["有哪些", "有什么", "包括"]):
            return "list"
        if any(kw in q for kw in ["为什么", "原因"]):
            return "cause"
        return "mixed"


# ============ Multi-Retrieval（统一入口）============

class MultiRetrieval:
    """
    多路检索器——所有检索走 MemoryManager.search()

    ✅ 接管前：各模块自己读文件，路径不统一
    ✅ 接管后：全部经由 MemoryManager，由它决定从哪个后端取

    检索策略：
    - keyword → MemoryManager.search(router="keyword")
    - graph   → MemoryManager.search(router="graph")
    - recent  → MemoryManager.search(router="recent")
    """

    def __init__(self, memory_manager=None):
        self.memory_manager = memory_manager
        self.decomposer = QueryDecomposer()
        if not memory_manager:
            self.graph = self._load_graph()
        else:
            self.graph = {}

    def _load_graph(self) -> Dict:
        if not GRAPH_FILE.exists():
            return {"entities": {}}
        with open(GRAPH_FILE) as f:
            return json.load(f)

    def retrieve_by_keyword(self, sub_query: str) -> List[Dict]:
        """关键词检索"""
        if self.memory_manager:
            items = self.memory_manager.search(sub_query, top_k=10, router="keyword")
            return [
                {
                    "type": item.type,
                    "id": item.id,
                    "name": item.content[:60],
                    "score": item.composite_score,
                    "source": "keyword"
                }
                for item in items
            ]

        # 降级：旧文件读取
        q = sub_query.lower()
        results = []
        for eid, entity in self.graph.get("entities", {}).items():
            score = sum(1 for w in q.split() if w in json.dumps(entity).lower())
            if score > 0:
                results.append({
                    "type": "entity", "id": eid,
                    "name": entity.get("name", eid),
                    "score": score, "source": "keyword"
                })
        results.sort(key=lambda x: -x["score"])
        return results[:5]

    def retrieve_by_graph(self, sub_query: str) -> List[Dict]:
        """知识图谱检索"""
        if self.memory_manager:
            items = self.memory_manager.search(sub_query, top_k=5, router="graph")
            return [
                {
                    "type": item.type,
                    "id": item.id,
                    "name": item.content[:60],
                    "neighbors": item.relations[:3],
                    "score": item.composite_score + 0.5,  # 图谱加权
                    "source": "graph"
                }
                for item in items
            ]

        # 降级：旧文件读取
        q = sub_query.lower()
        results = []
        for eid, entity in self.graph.get("entities", {}).items():
            if q in entity.get("name", "").lower():
                neighbors = []
                for rel in entity.get("relations", [])[:3]:
                    nid = rel.get("target")
                    neighbor = self.graph["entities"].get(nid, {})
                    neighbors.append({
                        "name": neighbor.get("name", nid),
                        "relation": rel.get("type"),
                        "context": rel.get("context", "")
                    })
                results.append({
                    "type": "entity_with_neighbors", "id": eid,
                    "name": entity.get("name", eid),
                    "neighbors": neighbors,
                    "score": 2.0, "source": "graph"
                })
        results.sort(key=lambda x: -x["score"])
        return results[:3]

    def retrieve_by_recent(self, sub_query: str) -> List[Dict]:
        """最近记忆检索"""
        if self.memory_manager:
            items = self.memory_manager.search(sub_query, top_k=5, router="recent")
            return [
                {
                    "type": item.type,
                    "id": item.id,
                    "name": item.content[:60],
                    "score": item.composite_score,
                    "source": "recent"
                }
                for item in items
            ]
        return []

    def multi_retrieve(self, sub_query: str) -> Dict:
        return {
            "sub_query": sub_query,
            "keyword_results": self.retrieve_by_keyword(sub_query),
            "graph_results": self.retrieve_by_graph(sub_query),
            "recent_results": self.retrieve_by_recent(sub_query),
            "intent": self.decomposer.identify_intent(sub_query)
        }


# ============ Rerank & Merge ============

class Reranker:
    """多路结果融合排序"""

    SOURCE_WEIGHTS = {"keyword": 0.4, "graph": 0.6, "recent": 0.3}

    def rerank(self, retrieval_results: List[Dict], top_k: int = 10) -> List[Dict]:
        merged = {}
        for retrieval in retrieval_results:
            for r in retrieval.get("keyword_results", []):
                rid = f"keyword:{r['id']}"
                if rid not in merged:
                    merged[rid] = {**r}
                else:
                    merged[rid]["score"] += r["score"] * 0.4
            for r in retrieval.get("graph_results", []):
                rid = f"graph:{r['id']}"
                if rid not in merged:
                    merged[rid] = {**r}
                else:
                    merged[rid]["score"] += r["score"] * 0.6
            for r in retrieval.get("recent_results", []):
                rid = f"recent:{r['id']}"
                if rid not in merged:
                    merged[rid] = {**r}
                else:
                    merged[rid]["score"] += r["score"] * 0.3
        sorted_results = sorted(merged.values(), key=lambda x: -x["score"])
        return sorted_results[:top_k]


# ============ Advanced RAG Query Engine ============

class AdvancedRAGQuery:
    """
    高级 RAG 查询引擎

    ✅ 接管后：所有检索经由 MemoryManager.search()
    """

    def __init__(self, memory_manager=None):
        self.retriever = MultiRetrieval(memory_manager)
        self.reranker = Reranker()
        self.decomposer = QueryDecomposer()
        self.memory_manager = memory_manager

    def query(self, user_query: str, top_k: int = 10) -> Dict:
        sub_queries = self.decomposer.decompose(user_query)
        retrieval_results = [self.retriever.multi_retrieve(sq) for sq in sub_queries]
        merged = self.reranker.rerank(retrieval_results, top_k)
        context = self._build_context(user_query, sub_queries, merged)
        return {
            "original_query": user_query,
            "sub_queries": sub_queries,
            "sub_query_count": len(sub_queries),
            "retrieval_results": retrieval_results,
            "merged_results": merged,
            "total_results": len(merged),
            "context": context
        }

    def _build_context(self, original: str, sub_queries: List[str],
                       results: List[Dict]) -> str:
        parts = [f"# 查询: {original}"]
        parts.append(f"## 查询分解（{len(sub_queries)}个子查询）")
        for i, sq in enumerate(sub_queries, 1):
            parts.append(f"{i}. {sq}")
        parts.append(f"\n## 检索结果（共 {len(results)} 条）")
        for i, r in enumerate(results, 1):
            parts.append(f"\n### {i}. {r['name']} ({r['type']})")
            parts.append(f"评分: {r['score']:.2f} | 来源: {r['source']}")
            if r.get("neighbors"):
                for n in r["neighbors"][:3]:
                    parts.append(f"  → {n.get('relation')}: {n.get('name')}")
        return "\n".join(parts)


# ============ 兼容性别名 ============

class GraphRAGQuery:
    """兼容性别名"""

    def __init__(self, memory_manager=None):
        self.advanced = AdvancedRAGQuery(memory_manager)

    def query(self, query: str, mode: str = "auto", top_k: int = 10) -> Dict:
        intent = self.advanced.decomposer.identify_intent(query)
        if mode == "auto":
            if intent in ["specific", "cause"]:
                return self.local_search(query, top_k)
            return self.global_search(query)
        if mode == "local":
            return self.local_search(query, top_k)
        return self.global_search(query)

    def local_search(self, query: str, top_k: int = 5) -> Dict:
        result = self.advanced.query(query, top_k)
        return {
            "query": result["original_query"],
            "mode": "local",
            "context": result["context"],
            "sub_queries": result["sub_queries"],
            "entities_found": result["total_results"]
        }

    def global_search(self, query: str) -> Dict:
        result = self.advanced.query(query, top_k=20)
        return {
            "query": result["original_query"],
            "mode": "global",
            "context": result["context"],
            "sub_queries": result["sub_queries"],
            "communities_found": result["sub_query_count"]
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Advanced RAG Query Engine")
    parser.add_argument("--search", "-s", metavar="QUERY", help="搜索查询")
    parser.add_argument("--mode", "-m", choices=["local", "global", "auto"],
                        default="auto", help="查询模式")
    parser.add_argument("--decompose", "-d", metavar="QUERY",
                        help="仅测试查询分解")
    args = parser.parse_args()

    if args.decompose:
        d = QueryDecomposer()
        subs = d.decompose(args.decompose)
        print(f"原始: {args.decompose}")
        print(f"意图: {d.identify_intent(args.decompose)}")
        print(f"分解: {subs}")
        return

    if args.search:
        engine = AdvancedRAGQuery()
        result = engine.query(args.search)
        print(f"\n🔍 查询: {result['original_query']}")
        print(f"📊 分解: {result['sub_queries']}")
        print(f"📦 结果: {result['total_results']} 条")
        print(result["context"])


if __name__ == "__main__":
    main()
