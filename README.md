# 🦐 OpenClaw Memory Architecture

> 坤哥的 Memory System——记忆主权架构

> ⚠️ **免责声明**：本项目由个人开发，食用前请先备份重要数据，以免数据丢失！
>
> **🚨 重要提醒**：
> - **记忆系统核心模块**（memory_protocol.py等）：小白可直接使用
> - **实时多Agent流水线**（realtime_agent/）：需要接入大模型API，**不建议小白直接部署**
> - 代码仅供参考学习，架构设计可作为设计参考
> - 
> -很抱歉，我刚因为个人原因，不小心将仓库文件进行了清除，我以后会更加小心，在此发表警戒我自己，我已经将现有架构进行备份！！！
## 核心理念

```
Single Source of Truth + Memory Protocol + Full Pipeline
```

## 模块总览（v6 → v1）

| 模块 | 版本 | 说明 |
|-----|------|------|
| `realtime_agent/` | v6 | 实时多Agent流水线：Listener意图分类 → Orchestrator任务分发 → Verifier质量验证 |
| `memory_scheduler.py` | v5 | 主动记忆调度：夜间consolidation + Forgetting Curve + 日志蒸馏 |
| `memory_protocol.py` | v4 | 记忆协议：HybridSimilarity + ContextBuilder + BudgetEngine |
| `memory_system_v2.py` | v3 | 统一入口：MemoryManager + 事件驱动冲突检测 |
| `base_memory_api.py` | v2 | 文件系统 + MemoryManager统一读写 |
| `profile_manager.py` | v1.1 | **用户画像v2：双层架构(Stable/Dynamic) + Anti-Bias + 权重因子** |
| `memory/` | v1 | 每日记忆日志 + 用户画像基础 |

## 架构演进

| 版本 | 状态 | 核心 |
|------|------|------|
| **v6** | **✅** | **实时多Agent流水线（Listener/Orchestrator/Verifier）** |
| **v5** | **✅** | **多Agent协作流水线 + 日志蒸馏机制** |
| **v4** | **✅** | **HybridSimilarity + FullPipeline + ContextBuilder工程化** |
| v3 | ✅ | Single Source of Truth + Protocol + Budget |
| v2 | ✅ | MemoryManager 统一入口（写入+读取） |
| **v1.1** | ✅ | **用户画像v2：双层Profile + Anti-Drift + 权重因子** |
| **v1** | ✅ | **文件系统 + 简单检索 + 用户画像基础** |

---

## v5 重大升级：多Agent协作 + 日志蒸馏

### 核心理念

```
Raw Logs (10k tokens)
       ↓
  [日志蒸馏Agent]  ← 一次小模型处理
       ↓
蒸馏摘要 (1k tokens)  ← 压缩10倍
       ↓
多Agent并行执行  ← 共享同一个蒸馏结果
       ↓
结果验收 + 整合汇报
```

### 完整流水线架构

```
用户输入
    ↓
┌─────────────────────────────────────────────────────┐
│  第一阶段：任务拆分（Router Agent）                      │
│                                                      │
│  "分析这季度东南亚Shopee各国家销售数据趋势"              │
│       ↓                                              │
│  意图识别 → 子任务拆分 → 并行规划                      │
│       ↓                                              │
│  [子任务1] [子任务2] [子任务3]                        │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│  第二阶段：日志蒸馏（可选，当日志量大时）                 │
│                                                      │
│  Raw Logs (10k tokens)                               │
│       ↓                                              │
│  Distiller Agent（小模型，一次处理）                    │
│       ↓                                              │
│  蒸馏摘要 (1k tokens):                               │
│  "- 印尼: GMV增长23%, 热销TOP3: 美妆/服饰/家居"        │
│  "- 马来: GMV增长15%, 热销TOP3: 电子/服饰/食品"         │
│  "- 菲律宾: GMV增长31%, 热销TOP3: 家居/美妆/玩具"       │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│  第三阶段：多Agent并行执行                            │
│                                                      │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐              │
│  │Agent1   │ │Agent2   │ │Agent3   │              │
│  │分析印尼  │ │分析马来  │ │分析菲律宾 │              │
│  │销售数据  │ │销售数据  │ │销售数据  │              │
│  └────┬────┘ └────┬────┘ └────┬────┘              │
│       └────────────┼────────────┘                    │
│                    ↓                                  │
│              结果合并                                  │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│  第四阶段：验收 + 汇报                               │
│                                                      │
│  ┌─────────────┐    ┌─────────────┐                │
│  │Verifier Agent│ → │Orchestrator  │                │
│  │结果一致性检查 │    │整合 + 二次验收│                │
│  │冲突检测     │    │最终输出      │                │
│  └─────────────┘    └─────────────┘                │
└─────────────────────────────────────────────────────┘
    ↓
最终输出
```

### Agent 职责表

| Agent | 职责 | 模型选择 |
|-------|------|---------|
| **Router** | 意图识别 + 任务拆分 | 小模型（DeepSeek） |
| **Distiller** | 日志蒸馏压缩 | 小模型（Qwen） |
| **Worker × N** | 并行处理子任务 | 按复杂度分配 |
| **Verifier** | 结果一致性 + 冲突检测 | 中等模型（MiniMax） |
| **Orchestrator** | 整合 + 二次验收 + 输出 | 主模型（GPT-4o / Claude） |

---

## 日志交叉验证提纯机制 ⭐ v5.1新增

### 核心原理

```
Day N:     记录日志
    ↓
Day N+1:  与 Day N 交叉验证 → 提纯摘要
    ↓
Day N+2:  删除 Day N 原日志（确认已提纯入库）
```

### 双层匹配策略

| 匹配类型 | 条件 | 置信度 | 处理 |
|---------|------|--------|------|
| **精确确认** | 两天完全相同 | 90% | 直接沉淀为稳定记忆 |
| **相似匹配** | 事件类型相同，细节不同 | 60-75% | 归一化后沉淀 |
| **新事件** | 只有Day N+1有 | 40% | 待下一轮验证 |
| **噪音** | 只有Day N有 | 15% | 可能是临时波动 |

### 归一化清洗

```
原文: "2026-04-15 ERROR Database connection failed: timeout"
  ↓ 去除时间戳/IP/端口
  ↓ 归一化错误类型
归一化: "数据库连接 失败: 超时"
```

### 效果

- **噪音过滤**：单日偶发事件不沉淀，防止污染记忆
- **稳定性确认**：连续出现的模式才视为稳定知识
- **自然遗忘**：日志在 N+2 天自动清理，不积累

---

## Token 降本策略

### 1. 日志蒸馏（效果最明显）

```
原始日志 10k tokens → 蒸馏后 1k tokens → 多Agent输入减少 90%
```

### 1.1 日志交叉验证（质量保障）

```
Day1 日志 ─┬─→ 精确匹配 ──→ 置信度 90% ──→ 稳定记忆
           └─→ 相似匹配 ──→ 置信度 60-75% ──→ 核心事件
Day2 日志 ─┘

只出现一次 → 置信度 40% → 待验证
两天都没 → 噪音 → 丢弃
```

### 2. 早停机制

```
Agent1 ──→ 结果 ──→ Verifier
  ↓                    ↑
  └──── 验收通过? ────┘
         ↓
        跳过 Agent2 / Agent3，直接输出
```

### 3. 模型分级

| 任务类型 | 推荐模型 | 原因 |
|---------|---------|------|
| 路由/拆分 | DeepSeek | 便宜又快 |
| 日志蒸馏 | Qwen | 中文理解好 |
| 子任务执行 | MiniMax | 性价比高 |
| 验收/整合 | GPT-4o/Claude | 需要强理解 |

### 4. 共享蒸馏上下文

```
旧: 每个Agent都加载完整 MEMORY.md (重复消耗)
新: 蒸馏一次，多Agent共享同一个记忆快照
```

### 5. 结果摘要而非完整返回

```
Agent返回: "天气晴，25度，适合出行"
不返回: "根据中国气象局数据显示，在副热带高压控制下..."
```

### 6. 预判机制

```
拆分前判断：这个任务真的需要多Agent吗？

"今天天气怎么样" → 单Agent就够
"分析东南亚Shopee全品类数据" → 多Agent才值得
```

---

## 现有模块在新架构中的作用

| 现有模块 | 在v5流程中的作用 |
|---------|----------------|
| `memory_scheduler.py` | consolidation = 日志蒸馏的定时任务 |
| `reflection_engine.py` | 反思 = 从记忆流提炼洞察的蒸馏逻辑 |
| `ContextBuilder` | 负责把蒸馏后的记忆拼给Agent |
| `MemoryProtocol` | 存储蒸馏后的摘要记忆 |
| `HybridSimilarity` | 验收时检测多Agent结果是否冲突 |

---

## 当前架构（v4 核心）

### 完整 Pipeline

```
用户 query
    ↓
┌─────────────────────────────────────┐
│  1. FullPipeline.plan(query)         │
│     自动决定路由：keyword / graph / recent │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  2. MemoryProtocol.search(router)    │
│     多路检索，结果合并                │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  3. ConfidenceGate.filter()          │
│     threshold=0.6 + fallback_to_recent │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  4. ContextBuilder.build()           │
│     去旧版 → 去重 → 排序 → 限数量     │
└─────────────────────────────────────┘
    ↓
LLM Context
```

### 核心模块

| 模块 | 职责 | 状态 |
|------|------|------|
| `HybridSimilarity` | 语义相似度（jaccard + fingerprint） | ✅ |
| `MemoryProtocol` | add/update/merge/delete 规则层 | ✅ |
| `BudgetEngine` | eviction_score 主动淘汰 | ✅ |
| `ConfidenceGate` | 置信度过滤 + fallback | ✅ |
| `ContextBuilder` | 标准流程构建上下文 | ✅ |
| `FullPipeline` | 串联以上所有模块 | ✅ |

---

## 重点模块详解

### 1. HybridSimilarity（混合语义相似度）

```python
similarity = 0.3 * jaccard + 0.7 * fingerprint

# jaccard：词级重叠（精确匹配）
# fingerprint：语义关联（Go/Golang 同义词）
# 结果稳定，不依赖单一信号
```

**为什么混合？**
- ❌ 只用 embedding → 误判率高
- ❌ 只用词匹配 → "时灵时不灵"
- ✅ 混合 → 两者加权，互相校正

### 2. MemoryProtocol（记忆规则层）

```python
# preference/belief 类 → update（不是新增）
add("坤哥喜欢简洁")
add("坤哥偏好简洁")  → update，不是 add

# observation 类 → merge（相似合并）
add("服务器IP是1.2.3.4")
add("IP是1.2.3.4")  → merge，不是并存

# 版本链可追溯
get_version_history(id)  → [v3, v2, v1]
```

### 3. BudgetEngine（主动约束）

```python
eviction_score = (
    importance * priority_weight * 0.5 +
    recency * 0.3 +
    access_frequency * 0.2
)

# 超过 max_items 时，淘汰分数最低的
# 不是被动触发，是主动约束
```

### 4. ContextBuilder（标准流程）

```python
def build():
    1. search()              # 检索
    2. confidence_filter()   # 置信度 < 0.6 过滤
    3. dedup_versions()      # 每个版本链只留最新
    4. dedup_similar()       # 相似内容去重
    5. sort_by_priority()   # core(3) > preference(2) > observation(1)
    6. limit(max_items)     # 限数量
    7. build_text()         # 截断到 max_tokens
```

### 5. FullPipeline（完整串联）

```python
pipeline = FullPipeline(protocol)
context = pipeline.run("坤哥服务器用什么语言")

# 内部自动执行：
# plan() → ["keyword", "recent"]
# search() → 多路合并
# filter_by_confidence() → 置信度过滤
# build_context() → 输出字符串
```

---

## 文件结构

```
scripts/
├── memory_protocol.py         # ⭐ v4 核心：Protocol + Budget + Pipeline
│   ├── HybridSimilarity        #   混合语义相似度
│   ├── MemoryItem              #   唯一真相单元
│   ├── MemoryBudget            #   预算配置
│   ├── BudgetEngine            #   主动淘汰引擎
│   ├── MemoryProtocol          #   add/update/merge/delete 规则
│   ├── ConfidenceGate          #   置信度过滤
│   ├── ContextBuilder          #   上下文构建器
│   └── FullPipeline            #   完整流程串联
│
├── embedding_lite.py           # 轻量语义相似度（独立模块）
├── memory_system_v2.py        # v2：统一入口
├── memory_conflict.py          # 事件驱动冲突检测
├── memory_scheduler.py         # 夜间 consolidation + forgetting（日志蒸馏前身）
├── memory_pager.py            # 三重触发内存分页
├── memory_auditor.py          # 冲突审计
├── graphrag_query.py          # RAG 查询引擎
└── reflection_engine.py       # 反思引擎（日志蒸馏逻辑）

# v5 多Agent相关（待实现）
├── multi_agent/
│   ├── router_agent.py        # 任务拆分 + 意图识别
│   ├── distiller_agent.py     # 日志蒸馏
│   ├── worker_agent.py        # 并行任务执行
│   ├── verifier_agent.py       # 结果验收
│   └── orchestrator_agent.py  # 整合 + 汇报
└── pipeline_v5.py            # v5 完整流水线
```

---

## 🚀 实时多Agent流水线 (v6)

> **⚠️ 部署前提**
> - 本模块需要**接入大模型API**（如MiniMax、DeepSeek等）才能正常工作
> - 需要**持续喂数据**优化意图分类和执行效果
> - **小白不建议直接部署**，建议先学习架构原理

### 核心亮点

- **监听Agent**：意图快速分类（<100ms）
- **编排Agent**：任务拆解 + 并行分发
- **验证Agent**：质量验证 + 最多2次打回 + 用户询问

> 💡 **相关功能**：用户画像动态同步 → 见下方 v1.1

### 架构图

```
用户消息
   ↓
┌──────────────────────────────────────┐
│  监听Agent (Listener)                 │
│  • 意图快速分类 (<100ms)              │
│  • 实体提取                           │
│  • 路由判断                           │
└────────────────┬─────────────────────┘
                 │
    ┌────────────┴────────────┐
    ↓                         ↓
 直接回复                    触发流水线
 (闲聊/简单)          ┌──────────────────────┐
                     │  编排Agent (Orchestrator) │
                     │  • 任务拆解               │
                     │  • 分发执行               │
                     │  • 结果整合               │
                     └───────────┬──────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ↓            ↓            ↓
              执行Agent1   执行Agent2   执行Agent3
              (Worker)    (Researcher)  (Creator)
                    └────────────┼────────────┘
                                 ↓
┌──────────────────────────────────────┐
│  验证Agent (Verifier)                 │
│  • 交叉验证结果                       │
│  • 质量评分                           │
│  • 不通过 → 打回重做（最多2次）        │
│  • 2次不行 → 询问用户                  │
└──────────────────────────────────────┘
```

### 核心规则

| 规则 | 说明 |
|-----|------|
| 验证打回 | 最多2次，2次都不行询问用户 |
| 用户偏好 | 记住用户选择，动态调整 |
| 路由判断 | 闲聊→直接回复，复杂→流水线 |

### 目录结构

```
scripts/realtime_agent/
├── __init__.py              # 集成接口
├── SKILL.md                 # Skill说明
├── pipeline.py              # 主流水线
├── common/
│   └── message_types.py     # 消息格式定义
├── listener/
│   └── intent_classifier.py # 意图分类 + 实体提取
├── orchestrator/
│   └── task_planner.py      # 任务拆解 + 分发执行（接大模型）
└── verifier/
    └── quality_gate.py       # 质量验证 + 用户交互
```

### 使用方式

```python
import sys
sys.path.insert(0, '/path/to/scripts')
from realtime_agent import should_use_pipeline, process_message

# 收到消息时
should, info = should_use_pipeline(message)
if should:
    result = process_message(message)
    # 使用result["content"]回复用户
```

### 待接入模块

- [ ] 真实搜索API（目前只有模型知识）
- [ ] 服务器操作接口（Worker执行）
- [ ] 飞书/消息通道集成
- [ ] 用户偏好持久化

---

## 🧠 用户画像 v1.1：双层架构 + Anti-Drift

### 核心问题：认知漂移（Profile Drift）

```
Day1随口说"试试Go"
     ↓
蒸馏 → 画像更新：偏好Go
     ↓
Day2系统强化Go相关记忆
     ↓
最终：系统"认为用户只喜欢Go" ❌
```

### 解决方案：双层Profile架构

```python
profile = {
    "stable": {...},   # 长期成立，高置信，很难被覆盖
    "dynamic": {...}   # 短期行为，可覆盖，可波动
}
```

| 层级 | 更新速度 | 置信度 | 可覆盖性 |
|------|---------|--------|----------|
| Stable | 慢 | 高 | 很难 |
| Dynamic | 快 | 低 | 可 |

### 稳定性验证规则

```python
# 进入stable的条件
if 连续出现 >= 2天 AND 置信度 >= 60%:
    更新stable
else:
    更新dynamic
```

### Anti-Bias 机制

```python
# 新记忆与画像冲突时
if memory 与 profile 冲突:
    降低profile置信度  # 系统不会固执，能自我修正
```

### 权重因子（不直接驱动删除）

```python
# 错误方式
❌ 不符合画像 → 删除

# 正确方式
✅ score += consistency_with_profile × 0.2
```

### 核心文件

- `profile_manager.py`：双层Profile管理器 + Anti-Bias + 权重因子

---

## 安全原则

⚠️ **所有公共仓库内容必须脱敏：**
- API Key → `YOUR_API_KEY`
- Webhook → `https://your-webhook.com/...`
- 服务器 IP → `YOUR_SERVER_IP`
- 域名 → `your-domain.com`
