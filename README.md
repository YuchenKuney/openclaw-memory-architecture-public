# 🦐 OpenClaw Memory Architecture

> 坤哥的 Memory System——记忆主权架构

> ⚠️ **免责声明**：本项目由个人开发，食用前请先备份重要数据，以免数据丢失！

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version: v7.0](https://img.shields.io/badge/Version-v7.0-blue.svg)]

## 🌟 简介

OpenClaw 记忆架构是一套用于 AI Agent 的**持久化记忆系统**，支持多层记忆管理、多智能体协作和实时进度追踪。

**v7 版本新增**：方案 A 主动进度反馈机制（cron 安全网 + 主动汇报），方案 B 子 Agent 主动推送机制（已落地：task_push.sh）

## 🏗️ 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    用户对话层                            │
│              (飞书 / Telegram / 群组)                    │
└──────────────────────┬────────────────────────────────┘
                       │ 消息路由
┌──────────────────────▼────────────────────────────────┐
│                   Leader Agent                          │
│  • 理解意图 · 分解任务 · 路由分发 · 质量把控            │
│  • 主动汇报进度（方案A）                                │
└────┬──────────────┬───────────────┬─────────────────────┘
     │              │               │
┌────▼────┐   ┌────▼────┐    ┌─────▼─────┐
│Researcher│  │ Creator │    │ Engineer │
│ (研究)  │  │ (创作)  │    │ (工程)   │
└────┬────┘   └────┬────┘    └─────┬─────┘
     │              │               │
     └──────────────┴───────────────┘
                       │
              ┌───────▼───────┐
              │  任务文件系统   │
              │  tasks/T-*.md │
              └───────────────┘
                       │
        ┌──────────────┴──────────────┐
        │         记忆存储层            │
        │  MEMORY.md · shared/ · memory/│
        └──────────────────────────────┘
```

## 📦 核心模块

### 1. 记忆层（scripts/）

| 文件 | 作用 |
|------|------|
| `memory_protocol.py` | 记忆协议：CRUD 操作规范 |
| `memory_lifecycle.py` | 记忆生命周期管理 |
| `memory_conflict.py` | 多源记忆冲突检测 |
| `memory_scheduler.py` | 定时记忆整理调度器 |
| `memory_pager.py` | 分页加载，防止上下文溢出 |
| `memory_auditor.py` | 记忆质量审计 |

### 2. 上下文构建（scripts/）

| 文件 | 作用 |
|------|------|
| `context_builder.py` | 构建 Agent 上下文 |
| `context_injector.py` | 动态注入上下文片段 |
| `embedding_lite.py` | 轻量级向量嵌入 |
| `graphrag_query.py` | 图检索增强查询 |

### 3. 知识管理（scripts/）

| 文件 | 作用 |
|------|------|
| `knowledge_graph.py` | 实体关系图构建 |
| `entity_extractor.py` | 实体提取器 |
| `reflection_engine.py` | 记忆反思引擎 |
| `rule_manager.py` | 运营规则管理器 |

### 4. 多智能体协作（scripts/multi_agent/）

```
multi_agent/
├── router_agent.py       # 任务路由：根据类型分发到合适 Agent
├── orchestrator_agent.py # 任务编排：多步骤协调
├── worker_agent.py       # 执行Agent：具体任务执行
├── distiller_agent.py    # 提炼Agent：信息压缩
└── verifier_agent.py     # 验证Agent：质量把关
```

### 5. 实时代理（scripts/realtime_agent/）

```
realtime_agent/
├── pipeline.py          # 实时管道
├── listener/
│   └── intent_classifier.py  # 意图分类
├── orchestrator/
│   └── task_planner.py      # 任务规划
├── verifier/
│   └── quality_gate.py     # 质量门禁
└── common/
    └── message_types.py     # 消息类型定义

### 6. 主动推送与调研脚本（scripts/）

| 文件 | 作用 |
|------|------|
| `task_push.sh` | 任务进度主动推送（每 step 完成即推送）|
| `serpapi_search.sh` | SerpAPI 电商调研（自动搜索 + 推送 + 摘要）|
| `rclone_sync_progress.sh` | 带进度的 Google Drive 同步脚本 |
| `tiktokshop_ecom_push.sh` | Google 搜索版 TikTok Shop 调研（备用）|
| `README.md` | 脚本使用说明文档 |

> **使用前需配置**：设置 `FEISHU_WEBHOOK` 和 `SERPAPI_KEY` 环境变量

## ⏱️ 进度反馈机制（v7 新增）

### 方案 A：Cron 安全网 + 主动汇报

**原理**：定时轮询任务状态，用户无需询问

```
┌─────────────────┐     每10分钟      ┌──────────────────────┐
│  Cron Scheduler │ ──────────────→ │ task_progress_check  │
│                 │                  │                      │
│  [CRON:TASK]   │                  │ 读取 tasks/*.md      │
└─────────────────┘                  │ 分析步骤进度         │
                                      │ 超时检测             │
                                      └──────────┬───────────┘
                                                  │
                                                  │ 发现任务进行中
                                                  ▼
                                      ┌──────────────────────┐
                                      │    主动推送到飞书     │
                                      │   "Shopee调研 40%"   │
                                      └──────────────────────┘
```

### 任务状态枚举

```python
STEP_STATUS = [
    "pending",              # 未开始
    "running",              # 进行中
    "waiting_for_input",     # 等待用户输入
    "waiting_for_tool",      # 等待工具返回
    "waiting_for_subtask",  # 等待子任务
    "done",                 # 完成
    "error",                # 失败
]
```

### 任务文件格式（tasks/T-YYYYMMDD-HHMM.md）

```yaml
# T-20260418-001: Shopee 爆款调研
status: in_progress
dispatched: 2026-04-18 08:00 HKT
route: feishu:direct:ou_xxx

## Steps
  - id: 1
    name: 数据搜索
    status: done
    progress: 1.0
    eta_seconds: 0
    last_update: "2026-04-18 08:00"

  - id: 2
    name: 整理报告
    status: running
    progress: 0.4
    eta_seconds: 60
    last_update: "2026-04-18 08:05"

  - id: 3
    name: 质量审核
    status: pending
    progress: 0
    eta_seconds: null
    last_update: null
```

### 进度展示

```
📋 Shopee 爆款调研
✅ Step 1 → 数据搜索 [██████████] 100%
🔄 Step 2 → 整理报告 [████░░░░░░] 40% 预计60秒
⏳ Step 3 → 质量审核 [░░░░░░░░░░░] 等待中
```

## 🔄 版本演进

| 版本 | 核心改进 |
|------|---------|
| v1-v4 | 基础记忆 CRUD |
| v5 | 多智能体协作层 + 冲突检测 |
| v6 | 图检索 + 反思引擎 |
| **v7** | **方案A主动进度反馈 + 任务状态结构化** |
| **v7** | **方案A + 方案B主动推送（task_push.sh + SerpAPI调研脚本）** |

## 🚀 快速开始

### 前置要求

```bash
# Python >= 3.10
python3 --version

# 依赖安装
pip install -r requirements.txt
```

### 运行记忆检查

```bash
# 检查记忆容量
python3 scripts/memory_check.py

# 执行记忆整理
python3 scripts/memory_scheduler.py

# 运行进度检查（方案A）
bash scripts/task_progress_check.sh
```

### 配置环境变量（主动推送 + 调研）

```bash
# 飞书 Webhook（必填）
export FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_WEBHOOK"

# SerpAPI Key（调研脚本需要，免费注册：https://serpapi.com/）
export SERPAPI_KEY="your_api_key_here"
```

### 运行电商调研（方案B主动推送）

```bash
# TikTok Shop 欧美爆款调研（自动推送进度 + 摘要）
SERPAPI_KEY=$SERPAPI_KEY bash scripts/serpapi_search.sh

# 带进度的 Google Drive 同步
RCLONE_REMOTE=yuchen RCLONE_DEST="备份/workspace" bash scripts/rclone_sync_progress.sh
```

## 📁 目录结构

```
openclaw-memory-architecture/
├── scripts/
│   ├── memory_*.py          # 记忆管理核心
│   ├── context_*.py         # 上下文构建
│   ├── knowledge_*.py        # 知识管理
│   ├── pipeline_v5.py        # v5主管道
│   ├── task_push.sh          # 任务进度主动推送（方案B）
│   ├── serpapi_search.sh     # SerpAPI 电商调研脚本
│   ├── rclone_sync_progress.sh  # 带进度的同步脚本
│   ├── README.md             # 脚本使用说明
│   ├── multi_agent/          # 多智能体协作
│   │   ├── router_agent.py
│   │   ├── orchestrator_agent.py
│   │   └── ...
│   └── realtime_agent/       # 实时代理
│       ├── pipeline.py
│       ├── listener/
│       ├── orchestrator/
│       └── verifier/
├── shared/
│   ├── domain/              # 领域知识
│   ├── errors/               # 错误解决方案
│   └── operations/            # 运营流程
│       └── task-schema-v2.md  # Task v2.0 规范
├── skills/                  # 可复用技能
├── memory/                   # 日记层
│   └── YYYY-MM-DD.md
├── tasks/                   # 任务状态（v7新增）
│   └── T-YYYYMMDD-HHMM.md
├── AGENTS.md                # Agent 操作规范
├── SOUL.md                 # Agent 灵魂定义
├── MEMORY.md               # 核心记忆
└── README.md               # 本文件
```

## 📖 设计理念

### 1. 容量限制

```
MEMORY.md    → ~2,200 字符
USER.md      → ~1,375 字符
超过 80% 警戒线 → 先精简再添加
```

### 2. 渐进式加载

不要一次性加载所有记忆，按需加载：

```
用户问产品 → 加载 products 相关记忆
用户问服务器 → 加载 servers 相关记忆
用户问运营 → 加载 operations 相关记忆
```

### 3. 结果交付准则（v7 铁律）

| 要求 | 说明 |
|------|------|
| **主动交付** | 完成后立即发送，不等用户问 |
| **说多久是多久** | "预计30秒"就是30秒，最多60秒 |
| **说到做到** | 说"稍等"的同时必须实际在工作 |

### 4. 状态语义化

不用模糊描述，用明确状态：

```
❌ "等待中" 
✅ waiting_for_input / waiting_for_tool / waiting_for_subtask
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)
