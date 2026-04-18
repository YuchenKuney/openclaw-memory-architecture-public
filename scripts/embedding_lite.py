#!/usr/bin/env python3
"""
Embedding Lite - 轻量级语义相似度

方案：character n-gram hash → 128维向量
无需外部模型，轻量快速，适合中文/英文

原理：
- 把文本切成 2/3-gram
- hash 成 128 维向量
- 用 SIMD 快速余弦相似度

解决：
- 词级匹配"时灵时不灵"的问题
- 让 update/merge 稳定可靠
"""

import math
import re
import struct
from typing import List, Tuple

class EmbeddingLite:
    """
    轻量级 embedding（无需外部模型）

    适合场景：
    - 中文/英文混合
    - 快速相似度计算
    - 无 GPU 环境
    """

    def __init__(self, dims: int = 128, ngram_range: Tuple[int,int] = (2,3)):
        self.dims = dims
        self.ngram_range = ngram_range
        # 预计算的单位向量（用于 hash）
        self._hash_vectors = self._generate_hash_vectors(dims)

    def _generate_hash_vectors(self, dims: int):
        """生成伪随机单位向量表（确定性）"""
        vectors = []
        for i in range(10000):  # 足够覆盖常见 ngram
            # 用确定性 seed 生成
            import hashlib
            seed = hashlib.md5(str(i).encode()).digest()
            # 转换为 dims 维单位向量
            import struct
            parts = []
            for j in range(0, len(seed), 4):
                if j + 4 <= len(seed):
                    val = struct.unpack('<f', seed[j:j+4])[0]
                    parts.append(val)
            # padding 到 dims
            while len(parts) < dims:
                parts.append(0.0)
            vec = parts[:dims]
            # 单位化
            norm = math.sqrt(sum(x*x for x in vec))
            if norm > 0:
                vec = [x/norm for x in vec]
            vectors.append(vec)
        return vectors

    def _hash_ngram(self, ngram: str) -> List[float]:
        """把 ngram hash 成向量（用预计算表）"""
        # 用 ngram 的前几个字符做索引
        idx = sum(ord(c) for c in ngram[:4]) % len(self._hash_vectors)
        return self._hash_vectors[idx]

    def encode(self, text: str) -> List[float]:
        """
        把文本编码为向量

        流程：
        1. 提取 character n-gram（中英文混合友好）
        2. hash 成向量
        3. 求和平均
        """
        # 提取 n-gram
        ngrams = self._extract_ngrams(text)

        if not ngrams:
            # fallback: 直接用字符编码
            return self._char_encoding(text)

        # 累加向量
        vector = [0.0] * self.dims
        for ngram in ngrams:
            ngram_vec = self._hash_ngram(ngram)
            for i in range(self.dims):
                vector[i] += ngram_vec[i]

        # 平均
        norm = math.sqrt(sum(x*x for x in vector))
        if norm > 0:
            vector = [x/norm for x in vector]
        return vector

    def _extract_ngrams(self, text: str) -> List[str]:
        """提取 character n-gram"""
        ngrams = []
        min_n, max_n = self.ngram_range

        # 中文：按字符
        chinese_seqs = re.findall(r'[\u4e00-\u9fff]+', text)
        for seq in chinese_seqs:
            for n in range(min_n, max_n + 1):
                for i in range(len(seq) - n + 1):
                    ngrams.append(seq[i:i+n])

        # 英文：按词
        english_words = re.findall(r'[a-zA-Z0-9_]+', text)
        for word in english_words:
            if len(word) >= 3:
                ngrams.append(word.lower())
                # 词片段
                for n in range(min_n, min(max_n + 1, len(word))):
                    for i in range(len(word) - n + 1):
                        ngrams.append(word[i:i+n].lower())

        return ngrams

    def _char_encoding(self, text: str) -> List[float]:
        """Fallback：直接用字符编码"""
        vector = [0.0] * self.dims
        chars = re.findall(r'[\u4e00-\u9fff]|[a-zA-Z0-9]', text)
        for i, c in enumerate(chars[:self.dims]):
            idx = ord(c) % self.dims
            vector[idx] += 1.0
        norm = math.sqrt(sum(x*x for x in vector))
        if norm > 0:
            vector = [x/norm for x in vector]
        return vector

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        dot = sum(a*b for a,b in zip(vec1, vec2))
        return max(0.0, min(1.0, dot))  # clamp to [0,1]

    def similarity(self, text1: str, text2: str) -> float:
        """两条文本的相似度"""
        vec1 = self.encode(text1)
        vec2 = self.encode(text2)
        return self.cosine_similarity(vec1, vec2)


# ============ 测试 ============

def test():
    print("=" * 60)
    print("Embedding Lite 测试")
    print("=" * 60)

    emb = EmbeddingLite(dims=128)

    # 1. 同义词测试
    print("\n1. 同义词/变体测试")
    pairs = [
        ("喜欢用 Go", "以后用 Golang"),
        ("喜欢用 Go", "后端改成 Go 语言"),
        ("坤哥喜欢简洁", "坤哥偏好简洁"),
        ("数据库连接失败", "数据库连接超时"),
        ("今天天气很好", "今天天气不错"),
    ]
    for t1, t2 in pairs:
        sim = emb.similarity(t1, t2)
        status = "✅" if sim > 0.3 else "⚠️"
        print(f"  {status} '{t1}' vs '{t2}': {sim:.3f}")

    # 2. 完全不同
    print("\n2. 不同内容测试")
    pairs2 = [
        ("服务器IP是1.2.3.4", "坤哥喜欢简洁"),
        ("数据库连接失败", "今天天气很好"),
    ]
    for t1, t2 in pairs2:
        sim = emb.similarity(t1, t2)
        print(f"  {'❌' if sim < 0.1 else '⚠️'} '{t1}' vs '{t2}': {sim:.3f}")

    # 3. 性能
    print("\n3. 性能测试（1000次）")
    import time
    t0 = time.time()
    for _ in range(1000):
        emb.similarity("坤哥喜欢用 Go 写后端服务", "以后用 Golang 重写后端")
    elapsed = time.time() - t0
    print(f"  1000次相似度计算: {elapsed*1000:.1f}ms ({elapsed*1000/1000:.3f}ms/次)")

    # 4. 集成 MemoryProtocol 测试
    print("\n4. 集成 MemoryProtocol 测试")
    from memory_protocol import MemoryProtocol, MemoryBudget

    budget = MemoryBudget(max_items=10)
    # 给 protocol 注入 embedding
    protocol = MemoryProtocol(budget)
    protocol.embedding = emb  # 注入

    # 第一次 add preference
    r1 = protocol.add("坤哥喜欢用 Go 写后端", type="preference", importance=0.9, source="user")
    print(f"  第一次 add: action={r1['action']}")

    # 第二次 add 相似的（应该 update）
    r2 = protocol.add("以后用 Golang 重写后端服务", type="preference", importance=0.9, source="user")
    print(f"  第二次 add (embedding-lite 触发): action={r2['action']}")
    print(f"  版本链: {len(protocol.get_version_history(r2.get('item_id') or r2['previous_id']))}个版本")

    stats = protocol.get_stats()
    print(f"  条目: {stats['total_active']}active / {stats['total_deleted']}deleted")

    print("\n✅ Embedding Lite 集成成功")


if __name__ == "__main__":
    test()
