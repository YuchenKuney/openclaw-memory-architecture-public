# 🦐 OpenClaw Memory Architecture

> 坤哥的 Memory System——记忆主权架构

> ⚠️ **免责声明**：本项目由个人开发，食用前请先备份重要数据，以免数据丢失！
>
> **Web4.0 AI Agent 沙箱无头浏览器安全声明**：Web4.0 模块铁律已写死在 `web4_cookie_injector.py` 代码里。禁止私自改装用于登录账号、越权访问、非授权爬取等违规行为。严禁爬取 PayPal、银行、邮箱、政府等私密页面。违规改装导致的一切法律后果由使用者自行承担，与项目开发者无关。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Contributors](https://img.shields.io/badge/Contributors-Welcome-green.svg)](CONTRIBUTORS.md)
[![Version: v10.0](https://img.shields.io/badge/Version-v10.0-blue.svg)]

## 🌟 简介

本项目是基于openclaw**MIT**开源协议做的二次开源架构

OpenClaw 记忆架构是一套用于 AI Agent 的**持久化记忆系统**，支持多层记忆管理、多智能体协作和实时进度追踪。

**v10 版本核心**：反黑箱通知铁律落地 + 看门狗自动拉起子 agent + progress_tracker ETA 实时追踪

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

### 7. 安全审计（clawkeeper/）

| 文件 | 作用 |
|------|------|
| `watcher.py` | inotify 文件系统监控 |
| `detector.py` | 风险检测引擎（4级风险）|
| `interceptor.py` | 拦截器 + Git Hooks |
| `notifier.py` | 飞书通知 |
| `auditor.py` | 审计日志 + 报告生成 |
| `config.py` | 动态配置管理 |
| `responder.py` | 自动审核响应器（处理允许/拒绝指令）|

### 8. Web4.0 AI 视觉（根目录）

| 文件 | 作用 |
|------|------|
| `web4_browser.py` | Playwright 无头浏览器 + 浏览器池 |
| `web4_container.py` | Linux Namespace 沙箱容器 |
| `web4_controller.py` | AI 研究接口（research函数）|
| `web4_cooker.py` | Cooking 注入引擎 |

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
| **v7** | **主动进度反馈 + 任务状态结构化** |
| **v8** | **反黑箱安全审计（AI行为全透明 + inotify监控 + 风险分级 + 人工审核）** |
| **v9** | **给AI装一双眼睛：Web4.0 AI Agent 沙箱无头浏览器 + Cooking 注入引擎** |
| **v10** | **反黑箱通知铁律落地：子 agent 实时推送「做了什么+怎么做+预计多久」+ 看门狗自动拉起** |

## 🛡️ 反黑箱安全审计（V8 核心）

> 坤哥的 Memory System——**AI 行为全透明，用户始终知道 Agent 在做什么**

### 什么是反黑箱？

传统 AI Agent：AI 在后台默默做事，用户不知道它做了什么、为什么要做、做了多少次。

**反黑箱 = AI 的每一个操作都对用户可见可查**

### Clawkeeper 架构

```
AI 操作 → inotify监控 → 风险检测 → 拦截/暂停/通知 → 用户审核 → 自动执行
```

### 风险等级与响应

| 等级 | 操作示例 | 响应方式 |
|------|---------|---------|
| 🔴 CRITICAL | 删除 AGENTS.md/SOUL.md/MEMORY.md | **立即拦截 + 立即通知** |
| 🚨 HIGH | 修改核心文件、删除核心目录 | **立即拦截 + 立即通知** |
| ⚠️ MEDIUM | push 到公共仓库 | **暂停 + 等用户审核** |
| 📝 LOW | 创建/修改普通文件 | 记录日志 |
| ✅ SAFE | 正常操作 | 放行 |

### 审核指令

| 用户回复 | AI 行为 |
|---------|--------|
| 「允许」 | 放行操作，AI 继续执行 |
| 「拒绝」 | 取消操作，自动回退（git checkout） |

### 覆盖范围

- ✅ **文件操作**：inotify 实时监控
- ✅ **cron 定时任务**：systemEvent 触发，通知用户
- ✅ **坤哥指令任务**：task_push.sh 每步推送
- ✅ **子 Agent 任务**：内置回调推送机制

### 通知示例

```
🔴 [CRITICAL] 尝试删除核心文件：AGENTS.md
文件: /workspace/AGENTS.md
操作: DELETE
风险等级: CRITICAL

处理方式: 操作已被拦截！AI 已暂停执行，等待坤哥处理。
回复「允许」放行 / 「拒绝」回退
```

### 快速部署

```bash
# 安装 Clawkeeper
cd clawkeeper
bash scripts/install.sh

# 启动监控
python3 -m clawkeeper.watcher

# 动态调整通知频率（0-关闭/CRITICAL/HIGH/MEDIUM/LOW）
python3 -c "from config import ClawkeeperConfig; \
    config = ClawkeeperConfig(); \
    config.set_notification_level('MEDIUM')"
```

## 🌐 Web4.0 AI Agent 沙箱无头浏览器（V9 核心）

> **给AI装一双眼睛** — AI 可以在沙箱隔离环境中自主浏览网页、提取内容、分析研究

### 核心架构

```
坤哥的 AI Agent（我）
    ↓ 调用 web4_controller.research()
web4_browser.py（浏览器池，3个并发实例）
    ↓ 运行在
web4_container.py（Linux Namespace 沙箱）
    ├── 独立网络栈 + IPv6 ULA 地址
    ├── Seccomp 系统调用过滤
    └── 沙箱外无法访问宿主机资源
    ↓ cooking 注入
web4_cooker.py（坤哥的烹饪配方）
```

### 文件说明

| 文件 | 职责 |
|------|------|
| `web4_browser.py` | Playwright 无头浏览器 + 浏览器池 + stealth 反爬 |
| `web4_container.py` | Linux Namespace 沙箱（网络/PID/挂载隔离） |
| `web4_controller.py` | AI 研究接口 `research(query, sites, cooking)` |
| `web4_cooker.py` | Cooking 注入引擎（坤哥配置 AI 研究行为） |

### Cooking 预设

| 预设 | 语言 | 策略 | 适用场景 |
|------|------|------|---------|
| `中文优先` | zh | standard | 中文资讯、最新 |
| `学术研究` | en | deep | arXiv / Nature 等学术站 |
| `快速扫描` | any | brief | 快速摸底 |
| `最新资讯` | zh | standard | 新闻、热点 |
| `技术深度` | en | deep | 深度技术分析 |
| `无图模式` | any | standard | 节省流量 |

### AI 用法示例

```python
# 坤哥说："研究量子计算最新进展，用中文优先"
from web4_controller import research

result = research(
    query="量子计算最新进展",
    sites=["nature.com", "arxiv.org"],
    cooking={
        "language": "zh",
        "strategy": "deep",
        "priority": "latest",
        "max_pages": 10,
    }
)

# 结果自动保存到 web4_sandbox/results/
# 每页提取：标题、正文、链接、截图、网络行为
```

### 隔离安全特性

- **Namespace 隔离**：PID / Network / Mount / IPC / UTS / User
- **Seccomp 过滤**：只允许 ~100 个安全系统调用，禁止 mount/sys_admin/ptrace
- **IPv6 ULA**：每容器分配唯一 `fd00:dead:beef:{hash}::1`
- **非 root 运行**：容器内用户映射为普通用户

---

## 🚀 快速开始

> 简单四步，开始使用 OpenClaw

```bash
# 1. 创建并激活虚拟环境
python3 -m venv venv && source venv/bin/activate

# 2. 克隆仓库
git clone https://github.com/YuchenKuney/openclaw-memory-architecture-public.git

# 3. 进入项目目录
cd openclaw-memory-architecture-public

# 4. 运行 Demo
python3 demo.py
# 运行电商记忆演进场景 Demo（展示 AI 逐步变聪明）
python3 demo.py --scenario

```

> 首次运行 demo.py 时会提示设置飞书机器人（可选），具体配置见下方。

### 飞书机器人配置（可选）

```bash
export FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_WEBHOOK"
export FEISHU_GROUP_ID="oc_xxxxxxxx"
```

> 不配置也可以正常运行 Demo，只是不会收到飞书通知。

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
├── clawkeeper/              # V8 安全审计（AI行为监控）
│   ├── watcher.py           # inotify 文件监控
│   ├── detector.py          # 风险检测引擎
│   ├── interceptor.py       # 拦截器
│   ├── notifier.py          # 飞书通知
│   ├── auditor.py           # 审计报告
│   ├── config.py            # 动态配置
│   └── scripts/
│       └── install.sh       # 安装脚本
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

## 🤝 贡献与支持者

欢迎提交 **Issue** 和 **Pull Request**！

如果您觉得项目有帮助，提交有效 Issue 被采纳后，可以加入 [CONTRIBUTORS.md](CONTRIBUTORS.md) 支持者名单。

**支持者荣誉**：GitHub 主页置顶展示，公平公开，无任何功能解锁或特权。

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)
