# 🦐 OpenClaw Memory Architecture

> AI Agent 自进化系统 — 记忆主权 × 反黑箱透明化 × Web4.0 安全铁律

[![Version: v12](https://img.shields.io/badge/Version-v12-blue.svg)](https://github.com/YuchenKuney/openclaw-memory-architecture-public)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎯 三大核心亮点

### 1️⃣ 三层记忆架构
> 借鉴 MemGPT 虚拟内存机制 + Generative Agents 反思架构

```
┌─────────────────────────────────────────────────────┐
│  Layer 1: MEMORY.md        长期记忆 · ~2KB始终加载    │
├─────────────────────────────────────────────────────┤
│  Layer 2: 知识图谱        Topic Files + Knowledge  │
│                          局部/全局查询              │
├─────────────────────────────────────────────────────┤
│  Layer 3: 日记层          Daily Logs + Memory Pager│
│                          动态换入换出               │
└─────────────────────────────────────────────────────┘
```

**MemGPT 三重触发分页机制**：
- 上下文压力 > 70% → 触发换出
- 检索失败率 > 30% → 触发换出
- 推理延迟上升 > 1.5x → 触发换出

详见 [MEMORY_LAYERS.md](MEMORY_LAYERS.md)

---

### 2️⃣ AI 自进化技能工厂（Skill Factory）

> AI 发现自身技能不足时，自动制造新 Skill，无需人工介入

```
用户给任务 → AI 判断缺技能 → 自动生成 SKILL.md → 执行 → 沉淀到 workspace
```

**核心流程**：
```
检测任务需求 → 判断现有 Skills 是否足够
    ↓ [不足]
分析缺什么能力 → 生成 SKILL.md（名称/描述/命令示例）
    ↓
创建执行脚本 → 动态加载 → Agent 自动发现并使用
```

| 版本 | 说明 |
|------|------|
| **版本 A** | 多服务器 + WireGuard VPN |
| **版本 B** | 单机自动判断+创造（推荐，开箱即用）|

---

### 3️⃣ 反黑箱透明化（全链路可见）

> 核心理念：AI 的每一个操作都对用户可见，不接受静默执行

| 透明等级 | 触发场景 | 推送方式 |
|---------|---------|---------|
| **L1 Webhook 卡片** | cron 任务执行 | 每步实时推送飞书群 |
| **L2 Task Schema** | 任务执行 | 进度% + step状态 + ETA |
| **L3 inotify** | 文件变化 | JSON → 飞书卡片 |
| **L4 Watchdog** | 进程存活 | 30秒心跳 |

**执行铁律**：接任务先说"分 X 步"，每步完成后立即 Webhook 推送，不在主会话刷进度。

---

## 🏗️ 系统架构

```
                    通信层（飞书 / Telegram）
                           │
                    ┌──────▼──────┐
                    │  Leader Agent │
                    │ 意图理解·任务分解│
                    │ 路由分发·质量把控 │
                    └──────┬───────┘
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
    │ Skill Factory│ │   记忆系统   │ │  安全审计   │
    │  AI自进化技能 │ │ MEMORY.md  │ │ clawkeeper │
    └─────────────┘ │ memory/    │ └─────────────┘
                     └────────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼──────┐ ┌───▼────┐ ┌───▼──────┐
        │cron任务监控│ │inotify │ │ Webhook  │
        │task_watchdog│ │文件监控│ │飞书卡片推送│
        └────────────┘ └────────┘ └──────────┘
```

详见 [ARCHITECTURE.md](ARCHITECTURE.md)

---

## 📁 核心模块

| 目录 | 说明 |
|------|------|
| `clawkeeper/` | 安全审计 — CVE扫描 / Skill.md审计 / 完整性校验 |
| `scripts/` | 核心脚本 — skill_factory / task_watchdog / feishu_progress |
| `skills/` | Skill 工厂示例 — 6个可复用的 Agent Skill |
| `shared/` | 知识库 — 错误解决方案 / 领域知识 / 最佳实践 |

---

## 🔧 快速开始

```bash
# 克隆仓库
git clone https://github.com/YuchenKuney/openclaw-memory-architecture-public.git
cd openclaw-memory-architecture-public

# 运行 Demo
python3 demo.py --demo 1        # 长连接审批
python3 demo.py --demo 2        # 回调地址审批
```

---

## 🛡️ 安全审计（Clawkeeper）

| 风险等级 | 颜色 | 操作示例 | 响应方式 |
|---------|------|---------|---------|
| 🔴 CRITICAL | 红 | 删除核心文件 | 立即拦截 + 立即通知 |
| 🚨 HIGH | 红 | 危险系统操作 | 沙箱隔离 + 飞书卡片审批 |
| ⚠️ MEDIUM | 黄 | push 到公共仓库 | 沙箱隔离 + 审批 |
| ✅ SAFE | 绿 | 正常操作 | 放行 |

---

## 📈 版本演进

| 版本 | 核心改进 |
|------|---------|
| v7 | 主动进度反馈 + 任务状态结构化 |
| **v8** | **反黑箱安全审计（AI行为全透明 + inotify监控）** |
| v9 | Web4.0 AI Agent 沙箱无头浏览器 |
| v10 | 反黑箱通知铁律落地 + 看门狗自动拉起子 agent |
| v11 | StepReporter 全链路透明化 |
| **v12** | **Skill Factory v12 完整实现 + AI 自进化技能工厂** |

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)