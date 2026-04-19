# OpenClaw Memory Architecture - 代码审核报告

> 审核日期：2026-04-19
> 仓库：https://github.com/YuchenKuney/openclaw-memory-architecture-public

---

## 一、整体架构

```
┌──────────────────────────────────────────────────────────────────┐
│                    OpenClaw Agent (Python)                         │
│                                                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ Orchestrator │  │ Memory System │  │ Clawkeeper (安全监控) │  │
│  │ (调度大脑)   │  │ v1 / v2      │  │                        │  │
│  └──────┬──────┘  └───────┬──────┘  └───────────┬────────────┘  │
│         │                │                      │                │
│         └────────────────┴──────────────────────┘                │
│                          │                                        │
│              ┌───────────▼───────────┐                          │
│              │    Memory Layers       │                          │
│              │  MEMORY.md (L1)        │                          │
│              │  shared/ (L2)           │                          │
│              │  memory/ (L3)           │                          │
│              └───────────────────────┘                          │
│                          │                                        │
│              ┌───────────▼───────────┐                          │
│              │  Knowledge Graph       │                          │
│              │  (实体关系图谱)          │                          │
│              └───────────────────────┘                          │
└──────────────────────────────────────────────────────────────────┘
```

---

## 二、目录结构

```
pub_arch/
├── AGENTS.md              # AI 行为规范（铁律）
├── ARCHITECTURE.md        # 系统架构设计文档
├── MEMORY_LAYERS.md       # 三层记忆机制说明
├── TRIGGER_MECHANISM.md  # 触发信号机制
├── rule_system.md         # 规则提取与管理
├── SECURITY.md            # 安全政策
│
├── *.py                   # 核心模块（根目录）
│   ├── orchestrator.py        # 统一调度大脑
│   ├── context_builder.py     # 上下文构建器
│   ├── context_injector.py    # 上下文注入器
│   ├── memory_lifecycle.py    # 记忆生命周期管理
│   ├── memory_watchdog.py     # 记忆看门狗（自动运维）
│   ├── knowledge_graph.py      # 知识图谱
│   ├── entity_extractor.py    # 实体提取器
│   ├── rule_manager.py        # 规则管理器
│   ├── log_distiller.py       # 日志提炼器
│   └── daily_distiller.py     # 每日提炼器
│
├── scripts/               # 脚本模块
│   ├── memory_protocol.py      # 记忆协议 v4（混合相似度）
│   ├── memory_system.py       # 可插拔记忆系统
│   ├── memory_system_v2.py    # 记忆主权系统 v2
│   ├── memory_pager.py       # 分页加载（防溢出）
│   ├── memory_conflict.py     # 冲突检测
│   ├── memory_scheduler.py    # 定时记忆整理
│   ├── memory_auditor.py      # 记忆质量审计
│   ├── base_memory_api.py     # 基础记忆 API
│   ├── embedding_lite.py      # 轻量级向量嵌入
│   ├── graphrag_query.py      # 图检索增强查询
│   ├── reflection_engine.py   # 反思引擎
│   ├── profile_manager.py     # Profile 管理
│   │
│   ├── cron-event-writer.py   # cron 事件写入（反黑箱）
│   ├── pre-push-check.sh      # 推送前脱敏扫描
│   ├── sync_memory.sh         # 记忆同步
│   ├── task_push.sh           # 任务推送
│   ├── task_progress_check.sh # 任务进度检查
│   └── realtime_agent/       # 实时多 Agent 流水线
│       ├── pipeline.py            # 主编排器
│       ├── listener/
│       │   └── intent_classifier.py  # 意图分类
│       ├── orchestrator/
│       │   └── task_planner.py       # 任务规划
│       └── verifier/
│           └── quality_gate.py       # 质量门禁
│
├── clawkeeper/           # 安全审查模块
│   ├── watcher.py            # inotify 文件系统监控
│   ├── detector.py           # 风险检测引擎（4级）
│   ├── notifier.py          # 飞书通知
│   ├── interceptor.py       # 危险操作拦截
│   ├── auditor.py           # 审计报告生成
│   ├── responder.py         # 「允许/拒绝」指令响应
│   ├── config.py            # 配置管理
│   ├── config_loader.py     # YAML/JSON 配置加载
│   ├── config.yaml          # 运行时配置
│   ├── start.sh             # 启动脚本
│   └── start_responder.sh   # 响应器启动脚本
│
├── memory/                # L3: 每日日志
│   └── YYYY-MM-DD-example.md
│
├── tasks/                # 任务文件系统
│   └── T-20260418-002.md
│
└── shared/                # L2: 共享知识
    ├── brands/
    ├── errors/
    │   └── solutions.md
    └── operations/
        ├── auto-dream.md
        ├── brief-templates.md
        ├── channel-map.md
        └── context-compression.md
```

---

## 三、核心模块代码逻辑

### 3.1 Orchestrator（调度大脑）

**文件**：`orchestrator.py`（327行）

**职责**：统一控制所有模块的执行顺序和上下文流向

**核心逻辑**：
```python
class Orchestrator:
    # 5大模块注册
    modules = {
        "rule_manager": {...},   # 规则管理
        "memory_manager": {...}, # 记忆管理
        "log_manager": {...},    # 日志管理
        "distiller": {...},      # 提炼引擎
        "watchdog": {...}        # 看门狗
    }

    # 执行流程
    def dispatch(user_input):
        1. Input Analyzer      # 分析用户输入
        2. Module Router       # 确定调用哪些模块
        3. Context Builder     # 构建上下文
        4. Execution Engine    # 执行模块
        5. Result Processor    # 处理结果
```

**关键设计**：
- 模块化注册机制，支持动态启用/禁用
- 按需调用，避免不必要的模块开销
- 统一的错误处理和恢复

---

### 3.2 Memory System v2（记忆主权）

**文件**：`scripts/memory_system_v2.py`（599行）

**核心数据结构**：
```python
class MemoryType(Enum):
    CORE          → MEMORY.md          # 核心长期记忆
    OBSERVATION   → daily logs         # 日常观察
    PREFERENCE    → Topic Files        # 用户偏好
    BEHAVIOR      → Topic Files        # 行为规律
    ERROR         → shared/errors/      # 错误教训
    ENTITY        → Knowledge Graph     # 实体
    RULE          → shared/rules/      # 规则
    TRANSACTIONAL → daily logs（不沉淀）# 事务性
```

**写入流程**：
```
MemoryManager.add(content, type)
    ↓
1. 类型判断（重要/经验/关系/检索）
    ↓
2. 目标路由
    ├── CORE → MEMORY.md
    ├── OBSERVATION/BEHAVIOR → Topic Files
    ├── ENTITY → Knowledge Graph
    └── ERROR → shared/errors/
    ↓
3. 一致性写入（多目标原子操作）
```

**解决的问题**：
- ❌ 双 memory 系统冲突 → ✅ 统一入口
- ❌ 不知道用哪套 memory → ✅ 只有 MemoryManager
- ❌ 写入路径不统一 → ✅ 强制路由

---

### 3.3 Memory Protocol v4（混合相似度检索）

**文件**：`scripts/memory_protocol.py`（777行）

**核心算法**：HybridSimilarity

```python
class HybridSimilarity:
    """
    混合相似度 = Jaccard（词级）× 0.3 + Semantic Fingerprint（语义）× 0.7
    """
    
    def tokenize(text):
        # 中文：字符 bigram + trigram
        # 英文：词 + 子词（2-gram, 3-gram）
        # 无需 jieba 等外部库
        
    def jaccard(text1, text2):
        # 词级 Jaccard 相似度
        
    def fingerprint(text):
        # 语义指纹：技术实体 + 意图向量
```

**Pipeline（检索流程）**：
```
plan    → 确定检索策略
  ↓
search  → 混合相似度搜索
  ↓
filter  → Confidence Gate（threshold=0.6）
  ↓
build   → 构建上下文
```

**eviction_score（遗忘评分）**：
```
eviction_score = importance × 0.5 + recency × 0.3 + access × 0.2
```

---

### 3.4 Knowledge Graph（知识图谱）

**文件**：`knowledge_graph.py`（7013行）

**核心结构**：
```python
class KnowledgeGraph:
    """
    实体关系图：
    - 节点：实体（人/事/物/概念）
    - 边：关系（has_a / part_of / caused_by / ...）
    - 属性：实体的特征
    """
    
    def add_entity(entity):
        # 添加实体到图
        
    def add_relation(entity1, relation, entity2):
        # 添加关系边
        
    def query(entity, depth=2):
        # 查询实体及其 N 度关系
```

---

### 3.5 Memory Watchdog（自动运维）

**文件**：`memory_watchdog.py`（503行）

**架构**：
```
Scheduler (cron)
    ↓
Decision Engine（判断是否执行）
    ↓
Executor（实际执行）
    ↓
Lock（文件锁，防冲突）
    ↓
Decision Log（记录原因）
```

**功能**：
1. 定时检查记忆状态
2. 自动决策是否需要清理/提炼
3. 执行必要的维护操作
4. 记录所有决策原因
5. 参数化配置（.watchdog.json）

---

### 3.6 Clawkeeper（安全审查）

**文件**：`clawkeeper/` 目录（8个模块）

**4层安全架构**：

```
┌─────────────────────────────────────────────────┐
│ Layer 1: watcher.py (inotify 实时监控)            │
│   - InotifyTree 毫秒级检测                       │
│   - PROTECTED_FILES: AGENTS.md / SOUL.md / ...   │
│   - PROTECTED_DIRS: tasks/ / memory/ / shared/    │
└────────────────────┬────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│ Layer 2: detector.py (风险等级评估)               │
│   - CRITICAL: 核心文件 DELETE → 自动备份 + 拦截   │
│   - HIGH: 修改核心身份文件                        │
│   - MEDIUM: cron-events/ DELETE                 │
│   - LOW/SAFE: 放行 + 日志                        │
└────────────────────┬────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│ Layer 3: notifier.py (飞书通知)                   │
│   - notify_cron_event() → cron 触发通知          │
│   - notify_risk_alert() → 风险告警               │
│   - notify_audit() → 审计摘要                    │
└────────────────────┬────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│ Layer 4: interceptor.py + responder.py           │
│   - interceptor: 危险操作拦截                     │
│   - responder: 「允许/拒绝」指令响应              │
└─────────────────────────────────────────────────┘
```

---

### 3.7 Realtime Agent Pipeline（实时多 Agent）

**文件**：`scripts/realtime_agent/pipeline.py`

**流程**：
```
用户消息
    ↓
1. Listener（接收 + 意图分类）
    ↓
2. Orchestrator（任务拆解 + 分发）
    ↓
3. Verifier（质量门禁验证）
    ↓
4. 不通过 → 重试（最多2次）
    ↓
5. 2次不行 → 询问用户
    ↓
6. 通过 → 回复用户
```

---

## 四、反黑箱安全机制

### 4.1 cron-events 链路（已打通）

```
cron 触发（09:00/15:50/18:30）
    ↓
cron-event-writer.py 写入 cron-events/*.json
    ↓
clawkeeper inotify 检测（毫秒级）
    ↓
detector.py → RiskLevel.SAFE
    ↓
notifier.py → 飞书卡片推送
```

### 4.2 推送前脱敏（pre-push-check.sh）

扫描 8 类敏感信息：
| 类型 | 模式 |
|------|------|
| GitHub PAT | `ghp_` + 36字符 |
| OpenAI API Key | `sk-` + 20+字符 |
| Feishu User ID | `ou_` + 32字符 |
| Feishu Chat ID | `oc_` + 32字符 |
| Feishu App Secret | `LnhA` + 30+字符 |

---

## 五、设计原则总结

| 原则 | 实现 |
|------|------|
| **无外部依赖** | 仅用 Python 标准库 |
| **单一数据源** | MemoryItem = 唯一真相 |
| **统一入口** | MemoryManager.add() 强制路由 |
| **可插拔架构** | Backend Adapter 支持多种存储 |
| **安全第一** | 4层防护 + 自动备份 |
| **透明可溯** | 所有决策写入日志 |
| **自动运维** | Watchdog 定时维护 |

---

## 六、代码质量评估

| 维度 | 评分 | 说明 |
|------|------|------|
| **架构设计** | ⭐⭐⭐⭐⭐ | 模块化清晰，职责分明 |
| **代码可读性** | ⭐⭐⭐⭐ | 注释详细，命名规范 |
| **安全性** | ⭐⭐⭐⭐⭐ | 4层防护，审计完整 |
| **容错性** | ⭐⭐⭐⭐ | 有 fallback，有锁 |
| **可维护性** | ⭐⭐⭐⭐ | 配置驱动，参数化 |

**亮点**：
- 纯标准库实现，零依赖
- 反黑箱机制完整（cron-events → clawkeeper → 飞书）
- 4层安全架构，层层防护

**改进建议**：
- memory_watchdog.py 的文件锁可升级为 fcntl.flock
- 部分模块缺少单元测试
- realtime_agent 目前较简单，可扩展为完整的多 Agent 协作
