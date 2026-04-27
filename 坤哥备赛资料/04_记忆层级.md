# Memory Layers - 三层记忆架构详解

> 借鉴 MemGPT 虚拟内存机制 + Generative Agents 反思架构

---

## 🏗️ 三层记忆架构

```
┌─────────────────────────────────────────────────────────┐
│           Layer 1: MEMORY.md (长期记忆)                  │
│  容量：~2KB，始终加载，上下文 40% 预警                   │
├─────────────────────────────────────────────────────────┤
│           Layer 2: Topic Files + Knowledge Graph        │
│  知识图谱组织，局部/全局查询                             │
├─────────────────────────────────────────────────────────┤
│           Layer 3: Daily Logs + Memory Pager           │
│  动态换入换出，三重触发机制                             │
└─────────────────────────────────────────────────────────┘
```

---

## 🔄 MemGPT 三重触发分页机制

**核心问题**：何时触发记忆换页？

### 触发公式
```
trigger = max(
    上下文压力,      # 1. context_pressure（超过70%）
    检索失败率,      # 2. retrieval_failure_rate（超过30%）
    推理延迟上升     # 3. reasoning_latency_increase（超过基准1.5x）
)
```

### 三重触发详解

| 触发器 | 计算方式 | 阈值 | 说明 |
|--------|---------|------|------|
| **上下文压力** | 当前 context 使用 % | > 70% | 上下文快满了，必须换出 |
| **检索失败率** | 滑动窗口内失败次数/总次数 | > 30% | 记忆找不到想要的，说明重要记忆被淹没了 |
| **推理延迟上升** | 当前平均延迟 / 基准延迟 | > 1.5x | 延迟突然上升，可能是记忆碎片化 |

### 滑动窗口追踪
- 窗口大小：默认 20 次检索
- 每条检索记录：(success: bool, latency_ms: float)
- 基准延迟：定期校准（取成功检索的中位数延迟）

### 换出策略
```
触发强度判断:
  - context > 80%: 换出 8~10 条（紧急）
  - context 70~80%: 换出 3~5 条（常规）
  - failure_rate > 30%: 换出 5 条
  - latency_ratio > 1.5x: 换出 4 条
```

### 召回机制
- 搜索时自动从 archival 召回相关记忆
- 召回后更新 recency_score
- 防止"僵尸记忆"（长期不被访问）

---

## 📊 评分公式（Generative Agents 启示）

```
composite_score = importance × 0.6 + recency × 0.3 + access_freq × 0.1

其中：
- importance: 基于类型（error=0.8, preference=0.7, behavior=0.6, trend=0.5, observation=0.3）
- recency: 1.0 - (days_ago / 30)，7天内满分，30天外接近0
- access_freq: min(1.0, access_count / 10)，访问10次封顶
```

---

## 🔍 GraphRAG 查询模式

### 局部查询（Local Search）
适合问具体实体的问题：
```
"坤哥的服务器是哪台？"
→ 找到实体 → 展开邻居 → 构建上下文
```

### 全局查询（Global Search）
适合问整体趋势/原则的问题：
```
"我的运营有什么规律？"
→ 找到相关社区 → 使用社区摘要 → 归纳回答
```

---

## 💡 与 LangChain Memory 的对比

| LangChain Memory | 本架构对应 |
|-----------------|-----------|
| Buffer Memory | L3 Daily Logs（原始记录）|
| Summary Memory | L1 MEMORY.md（提炼后的核心记忆）|
| Entity Memory | L2 Topic Files（实体知识）|
| Knowledge Graph Memory | Knowledge Graph（实体关系图谱）|

---

## 🚀 实践建议

### 1. 保持 L1 精简
- 每条记忆 ≤150 字符
- 只保留"永久性"信息
- 定期将 L3 提炼到 L1

### 2. L2 按需丰富
- 品牌知识：shared/brands/
- 错误教训：shared/errors/
- 运营流程：shared/operations/

### 3. L3 保持原始
- 完整记录，不删改
- 定期归档（超过30天的移入 archive/）
- 使用语义搜索而非全文加载

### 4. 三重触发监控
```bash
# 查看诊断
python3 scripts/memory_pager.py --status

# 模拟上下文压力测试
python3 scripts/memory_pager.py --check 75

# 强制换出
python3 scripts/memory_pager.py --evict 5
```

---

## 🔄 记忆流转

```
用户对话
    ↓ 记录
L3 Daily Logs（原始）
    ↓ 日志提炼（log_distiller.py）
L2 Topic Files（知识沉淀）
    ↓ 知识提炼（rule_manager.py）
L1 MEMORY.md（长期记忆）
    ↓ 反思（reflection mechanism）
Belief（信念体系）
    ↓ 三重触发评估
Memory Pager ←→ Archival Storage
```

---

_设计参考：MemGPT (三重触发分页)、GraphRAG (知识图谱查询)、Generative Agents (记忆流评分)_
