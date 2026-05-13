# 🦐 OpenClaw Memory Architecture

> AI Agent 自进化系统 — 记忆架构 × 反黑箱透明化 × Web4.0 安全铁律 × 神经传输层

[![Version: v12](https://img.shields.io/badge/Version-v12-blue.svg)](https://github.com/YuchenKuney/openclaw-memory-architecture-public)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎯 四大核心亮点

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

### 4️⃣ Web4.0 AI Agent 沙箱

> **给 AI 装一双眼睛** — AI 在沙箱隔离环境中自主浏览网页、分析研究

**隔离安全特性**：
- **Namespace 隔离**：PID / Network / Mount / IPC / UTS / User
- **Seccomp 过滤**：只允许 ~100 个安全系统调用
- **Cookie 铁律**：只注入 preference cookies，禁止登录态 tokens
- **robots.txt 合规**：铁律五，fetch_page 集成检查
- **审计日志**：铁律六，IronRuler.audit_log() 全量记录

**Stealth 反检测（17 项）**：移除 navigator.webdriver、Canvas 加噪、WebGL 渲染器伪装、HardwareConcurrency 仿真等。实测 Bing 搜索从 0 结果 → 34,600 条真实数据。

**Web4.0 六条铁律**：

| 铁律 | 内容 |
|------|------|
| 铁律一 | Cookie 只读，登录态 tokens 禁止注入 |
| 铁律二 | 禁止账号注册/登录操作 |
| 铁律三 | 禁止 PayPal/银行/邮箱等敏感页面访问 |
| 铁律四 | 速率限制（3秒间隔 + 50次/上限）|
| 铁律五 | robots.txt 合规检查 |
| 铁律六 | 审计日志全量记录 |

详见 [web4_IRON_RULES.md](web4_IRON_RULES.md)（私有仓库）

---

### 5️⃣ 神经传输层（Neural Tunnel Protocol）

> 自研 UDP 私有神经隧道，彻底替代 WireGuard

**核心特性**：

| 特性 | 实现 |
|------|------|
| **架构** | 全中心化 Hub-Spoke，所有流量收敛到中枢 |
| **密钥交换** | Noise Protocol (X25519 + HKDF-SHA256) |
| **端到端加密** | ChaCha20-Poly1305 AEAD |
| **完整性** | HMAC-SHA256 防篡改 |
| **防重放** | 时间戳（5分钟窗口）+ 序列号 |
| **分片** | 自动分片重组，MTU=1400 |
| **重传** | ARQ滑动窗口，最多5次重传 |
| **心跳** | 30秒保活，5分钟超时踢出 |
| **TUN网卡** | 虚拟网卡，系统级流量劫持 |

**握手流程（2-RTT）**：
```
Node                        Hub
──────────────────────────────────
INIT(s_pub, e_pub)     ──→  (静态+临时公钥)
                     ←──  ACK(re_pub, es_proof)
FIN(e_pub, ee, se)    ──→  (完成证明)
```

**安全属性**：
- 前向保密：临时密钥保护，私钥泄露不影响历史
- 双向认证：静态密钥实现节点身份验证
- 防中间人：双方DH贡献确保密钥协商安全

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
           ┌─────────────────┼─────────────────┐
           │                 │                 │
    ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
    │ Neural Tunnel│  │  Web4.0     │  │  反黑箱透明化 │
    │  UDP神经隧道 │  │  AI沙箱浏览器│  │  全链路可见  │
    └─────────────┘  └─────────────┘  └─────────────┘
```

---

## 📁 核心模块

| 目录 | 说明 |
|------|------|
| `clawkeeper/` | 安全审计 — CVE扫描 / Skill.md审计 / 完整性校验 |
| `scripts/` | 核心脚本 — skill_factory / task_watchdog / feishu_progress |
| `skills/` | Skill 工厂示例 — 6个可复用的 Agent Skill |
| `shared/` | 知识库 — 错误解决方案 / 领域知识 / 最佳实践 |
| `web4/` | Web4.0 沙箱浏览器 — 隔离环境 / Stealth反检测 / 六条铁律 |
| `neural/` | 神经传输层 — UDP隧道 / Noise协议 / TUN网卡劫持 |

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