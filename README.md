# 🦐 OpenClaw Memory Architecture

> AI Agent 自进化系统 — 记忆主权 + 反黑箱透明化 + Web4.0 安全铁律

[![Version: v12](https://img.shields.io/badge/Version-v12-blue.svg)](https://github.com/YuchenKuney/openclaw-memory-architecture-public)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎯 三大核心亮点

### 1️⃣ AI 自进化技能工厂（Skill Factory）

AI 发现自身技能不足时，**自动制造新 Skill**，无需人工介入。

```
用户给任务 → AI 判断缺技能 → 自动生成 SKILL.md → 执行 → 沉淀到 workspace
```

| 版本 | 说明 |
|------|------|
| **版本 A** | 多服务器 + WireGuard VPN（主服务器 ↔ 新加坡）|
| **版本 B** | 单机自动判断 + 创造（推荐，开箱即用）|

详见 [skill-factory/](skill-factory-repo/)

---

### 2️⃣ 反黑箱透明化（全链路飞书卡片推送）

**核心理念**：AI 的每一个操作都对用户可见，不接受静默执行。

#### 四级透明化机制

| 等级 | 触发场景 | 透明度 |
|------|---------|--------|
| **Webhook 卡片** | cron 任务执行 | 每步实时推送飞书群，坤哥躺着看 |
| **Task Schema v2.0** | 任务执行 | 带进度%、step状态、ETA |
| **inotify 监控** | 文件变化 | cron-events/ JSON → inotify → 飞书卡片 |
| **Watchdog 心跳** | 进程存活 | 30秒心跳，死活都报 |

#### 反黑箱执行铁律

- 接到任务先说"**分 X 步**"，每步完成后**立即 Webhook 推送**
- 不在主会话刷进度消息，**所有进度走飞书卡片**
- 状态明确：不用"等待中"，用 `pending / running / waiting_for_input / done / error`
- 完成立即交付，不等用户追问

---

### 3️⃣ Web4.0 安全铁律体系

AI 在沙箱隔离环境中自主浏览网页，必须遵守铁律：

| 铁律 | 内容 |
|------|------|
| 铁律一 | Cookie 只读，登录态 tokens 禁止注入 |
| 铁律二 | 禁止账号注册/登录操作 |
| 铁律三 | 禁止 PayPal/银行/邮箱等敏感页面访问 |
| 铁律四 | 速率限制（3秒间隔 + 50次/上限）|
| **铁律五** | **robots.txt 合规检查** |
| **铁律六** | **审计日志全量记录** |

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     通信层（飞书 / Telegram）                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    Leader Agent                               │
│         意图理解 · 任务分解 · 路由分发 · 质量把控               │
└──────┬──────────────┬──────────────┬────────────────────────┘
       │              │              │
┌──────▼─────┐  ┌─────▼─────┐  ┌─────▼──────┐
│Skill Factory│  │ 记忆系统  │  │ 安全审计    │
│ AI自进化技能│  │MEMORY.md │  │ clawkeeper │
└─────────────┘  │memory/   │  └────────────┘
                 └──────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
  ┌─────▼─────┐     ┌─────▼─────┐     ┌─────▼──────┐
  │cron任务监控│     │ inotify   │     │ Webhook    │
  │task_watchdog│   │文件监控   │     │飞书卡片推送│
  └───────────┘     └───────────┘     └────────────┘
```

---

## 📁 核心目录

```
openclaw-memory-architecture/
├── clawkeeper/                  # 安全审计
│   ├── detector.py             # 正则 + LLM 语义双层风险检测
│   ├── interceptor.py           # 四级分层响应 + 沙箱隔离
│   ├── reply_handler.py        # 飞书卡片回调处理
│   ├── notifier.py             # 飞书通知 + StepReporter
│   ├── auditor.py              # 主动扫描（CVE/完整性）
│   └── watcher.py              # inotify 文件变化监控
├── scripts/
│   ├── skill_factory.py         # AI 自进化技能工厂
│   ├── task_watchdog.py        # 看门狗（进程守护）
│   ├── task_monitor.py         # 任务状态监控
│   ├── task_monitor_agent.py   # 任务汇报 Agent
│   ├── cron-event-writer.py    # cron 事件写入
│   ├── feishu_progress.py      # 飞书进度推送
│   └── session_refiner.py       # 会话摘要优化
├── skill-factory-repo/           # Skill Factory 独立仓库
│   ├── v12_skill_factory/      # 集成版（版本 A）
│   └── skill_factory_standalone/ # 独立版（版本 B，推荐）
├── memory/                      # 日记层
│   └── YYYY-MM-DD.md
├── v12_skill_factory/           # 主仓集成版
├── web4_*.py                   # Web4.0 视觉模块
├── AGENTS.md                   # Agent 操作规范
├── ANTI_BLACKBOX.md            # 反黑箱文档
├── web4_IRON_RULES.md         # Web4.0 铁律（硬编码版）
└── SECURITY.md                # 安全政策 + 负责任披露
```

---

## 🚀 快速开始

```bash
# 克隆仓库
git clone https://github.com/YuchenKuney/openclaw-memory-architecture-public.git
cd openclaw-memory-architecture-public

# 运行 Demo
python3 demo.py --demo 1        # Demo 1：长连接审批
python3 demo.py --demo 2        # Demo 2：回调地址审批
python3 demo.py --demo ecommerce --scenario  # 电商记忆演进

# 查看 Skill Factory 独立仓库（推荐）
cd skill-factory-repo/skill_factory_standalone
```

### Demo 审批系统

**Demo 1（长连接）**：每5秒轮询飞书群消息，检测 `@审批机器人` + 文字命令。简单但有5秒延迟。

**Demo 2（回调地址）**：公网 HTTP 服务器接收飞书卡片按钮回调，实时弹窗 + toast。需公网地址 + 飞书事件订阅。

**核心 API**：`wait_for_approval(action_id, message, level, timeout=300)` — AI 执行危险操作前必须调用此方法阻塞等待审批。

---

## 🔧 Skill Factory 详解

### 核心流程

```
检测任务需求
    ↓
判断现有 Skills 是否足够
    ↓ [不足]
自动分析缺什么能力
    ↓
生成 SKILL.md（名称/描述/命令示例）
    ↓
创建执行脚本
    ↓
动态加载到 workspace/skills/
    ↓
Agent 自动发现并使用新技能
```

### 版本对比

| | 版本 A（多服务器）| 版本 B（单机）|
|--|--|--|
| VPN | WireGuard 主↔新加坡 | 无 |
| 适用场景 | 多机器协作 | 单机开箱即用 |
| 推荐度 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 🛡️ 安全审计机制

### 四级风险响应

| 等级 | 颜色 | 操作示例 | 响应方式 |
|------|------|---------|---------|
| 🔴 CRITICAL | 红 | 删除核心文件 | 立即拦截 + 立即通知 |
| 🚨 HIGH | 红 | 危险系统操作 | 沙箱隔离 + 飞书卡片审批 |
| ⚠️ MEDIUM | 黄 | push 到公共仓库 | 沙箱隔离 + 审批 |
| 📝 LOW | 蓝 | 创建普通文件 | 沙箱隔离 + 记录 |
| ✅ SAFE | 绿 | 正常操作 | 放行 |

### 透明化监控事件

```
llm_input   → 模型输入
tool_call   → 工具调用
tool_result → 工具结果
ai_message  → AI 回复
system_action → 系统动作
```

---

## 📈 版本演进

| 版本 | 核心改进 |
|------|---------|
| v1-v6 | 基础记忆 + 多智能体协作 |
| **v7** | **主动进度反馈 + 任务状态结构化** |
| **v8** | **反黑箱安全审计（AI行为全透明 + inotify监控 + 风险分级）** |
| **v9** | **Web4.0 AI Agent 沙箱无头浏览器 + Cooking 注入引擎** |
| **v10** | **反黑箱通知铁律落地 + 看门狗自动拉起子 agent** |
| **v11** | **StepReporter 全链路透明化 + Web4.0 stealth 加强** |
| **v12** | **Skill Factory v12 完整实现 + AI 自进化技能工厂** |

---

## 🌐 Web4.0 AI Agent 沙箱

> **给 AI 装一双眼睛** — AI 在沙箱隔离环境中自主浏览网页、分析研究

### 隔离安全特性

- **Namespace 隔离**：PID / Network / Mount / IPC / UTS / User
- **Seccomp 过滤**：只允许 ~100 个安全系统调用
- **Cookie 铁律**：只注入 preference cookies，禁止登录态 tokens
- **robots.txt 合规**：铁律五，fetch_page 集成检查
- **审计日志**：铁律六，IronRuler.audit_log() 全量记录

### Stealth 反检测（17 项）

移除 navigator.webdriver、Canvas 加噪、WebGL 渲染器伪装、HardwareConcurrency 仿真等。实测 Bing 搜索从 0 结果 → 34,600 条真实数据。

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！有效 Issue 被采纳后可加入 [CONTRIBUTORS.md](CONTRIBUTORS.md)。

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)
