# References - 参考项目

> 本项目借鉴了以下开源项目和研究论文的设计理念

---

## 📚 参考项目

### 1. MemGPT
**仓库**: https://github.com/MemGPT/MemGPT

**核心思想**: 
将 LLM 的记忆管理类比为 OS 的虚拟内存管理。通过层级存储（Working Memory / Recent Memory / Archival Memory）和自动换页机制，解决 LLM 上下文窗口有限的问题。

**本项目借鉴**:
- 三层记忆的层次划分
- 上下文溢出时的换页/压缩策略
- 记忆优先级排序机制

---

### 2. GraphRAG (Microsoft)
**仓库**: https://github.com/microsoft/graphrag

**核心思想**:
基于知识图谱的 RAG 系统。不同于简单的向量相似度搜索，GraphRAG 通过从原始文本中提取实体和关系，构建知识图谱，并利用社区检测实现全局推理。

**核心能力**:
- **Local Search**: 围绕特定实体的局部查询
- **Global Search**: 利用社区摘要回答概括性问题
- **DRIFT Search**: 混合模式

**本项目借鉴**:
- 知识图谱作为 L2 记忆的存储结构
- 社区检测实现层级组织
- 全局/局部查询分离的设计

---

### 3. Generative Agents (Stanford)
**论文**: https://arxiv.org/abs/2304.03442

**核心思想**:
25 个生成式智能体在类 Sims 的沙盒环境中生活，具备观察、规划、反思能力。通过自然语言记忆记录、动态检索和反思提炼，模拟可信的人类行为。

**核心架构**:
```
观察 (Observation) → 记忆 (Memory) → 反思 (Reflection) → 信念 (Belief) → 规划 (Planning)
```

**本项目借鉴**:
- 反思机制（Reflection）将原始记忆升华为信念
- 置信度评估体系
- 动态规划能力

---

### 4. LangChain Memory
**文档**: https://python.langchain.com/docs/concepts/memory/

**核心思想**:
LangChain 的记忆系统提供了多种 Memory 类型：
- **Buffer Memory**: 原始对话历史
- **Summary Memory**: 对话摘要
- **Entity Memory**: 实体记忆
- **Knowledge Graph Memory**: 知识图谱记忆

**本项目借鉴**:
- 记忆类型的分类方法
- 与 LangChain 等框架的集成思路

---

## 🔬 相关论文

| 论文 | 年份 | 核心贡献 |
|------|------|---------|
| Generative Agents | 2023 | 生成式智能体架构 |
| GraphRAG | 2024 | 知识图谱增强 RAG |
| MemGPT | 2024 | 虚拟内存记忆管理 |
| MetaGPT | 2023 | 多智能体协作框架 |

---

## 🤝 贡献者

本项目为开源架构设计，欢迎提交 Issue 和 PR 讨论实现细节。

---

_Last updated: 2026-04-17_
