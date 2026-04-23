# 🦐 OpenClaw Memory Architecture

> 坤哥的 Memory System——记忆主权架构

> ⚠️ **免责声明**：本项目由个人开发，食用前请先备份重要数据！
>
> **Web4.0 AI Agent 沙箱无头浏览器安全声明**：铁律已写死在 `web4_cookie_injector.py` 代码里。禁止私自改装用于登录账号、越权访问、非授权爬取等违规行为。严禁爬取 PayPal、银行、邮箱、政府等私密页面。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Contributors](https://img.shields.io/badge/Contributors-Welcome-green.svg)](CONTRIBUTORS.md)
[![Version: v11.11](https://img.shields.io/badge/Version-v11.11-blue.svg)]

## 🌟 简介

本项目是基于 OpenClaw **MIT** 开源协议的二次架构扩展。

**v11.7 版本核心**：飞书审批联动 + Web4.0 加强版 stealth（Bing 搜索从 0→34,600 条真实数据）

- **飞书审批联动**：危险操作被拦截 → 飞书卡片按钮 → toast 弹窗 → AI 继续执行
- **StepReporter**：AI 每步操作主动汇报到飞书群（全链路透明化）
- **Web4.0 stealth**：17 项反检测措施，绕过 Bing/Google 人机检测

## 🔥 v11.11 Bug 修复（2026-04-23）

**6 个 Bug 修复 + 脱敏处理**：

| Bug | 文件 | 严重度 | 修复内容 |
|-----|------|--------|---------|
| Bug 2 | `interceptor.py` | 🔴 | `reject()` 添加 `rollback` 参数，修复 `TypeError: reject() got unexpected keyword argument 'rollback'` |
| Bug 6 | `interceptor.py` | 🔴 | `wait_for_approval` 改为指数退避轮询（0.5s 起步→5s 上限），解决固定 2s 轮询 CPU 空转问题 |
| Bug 6 | `reply_handler.py` | 🔴 | `get_status()` 每次重新 `_load()` 文件，修复跨进程状态同步失效 |
| Bug 4 | `detector.py` | 🟡 | 删除死代码 `_should_notify()`（从未被调用）；装饰器参数名加下划线 `_level`/`_mode` 避免遮蔽 |
| Bug 5 | `auditor.py` | 🟡 | 正则加 `\b` 词边界，消除 `request.POST`/`curly`/`curly_braces` 误报 |
| 脱敏 | `interceptor.py` | 🔒 | 硬编码 `app_secret` 改为 `os.environ.get()` 环境变量读取 |

**影响**：审批链路更稳定，扫描误报率降低，敏感信息不再泄漏到代码中。

## 🔥 v11.10 Bug 修复（2026-04-22）

**cron-events 监控链路 bug 修复**：
- **Root Cause**：创建新文件时 inotify 触发 `IN_CREATE`+`IN_OPEN`+`IN_MODIFY`+`IN_CLOSE_WRITE`，但 `add_watch` 只注册了 `IN_MODIFY`，漏掉 `IN_CLOSE_WRITE`，导致 cron 事件文件永远不被捕获
- **Fix**：`INOTIFY_EVENTS` 新增 `IN_CLOSE_WRITE → MODIFY` 映射
- **Fix**：两处 `add_watch` 调用新增 `IN_CLOSE_WRITE|IN_OPEN|IN_ACCESS` 标志位
- **Fix**：`notifier.py` 字段映射修正：`event→job_name`、`action→status`、`timestamp→triggered_at`（兼容 `cron-event-writer.py` 写入的 JSON 格式）

**影响**：18:30 记忆同步等 cron 定时任务现在能正确触发飞书群通知

## 🔥 v11.9 安全升级（2026-04-22）

**Web4.0 铁律体系全面升级**：
- 🔥🔥🔥🔥🔥 **铁律五：robots.txt 合规检查** — `is_allowed_by_robots()` 集成到 `fetch_page()`，Shopee `/user/` 等路径 robots.txt disallow 时自动拦截
- 🔥🔥🔥🔥 **铁律六：审计日志** — `IronRuler.audit_log()` 记录所有铁律拦截事件，保留最近 500 条
- 🔥🔥🔥🔥 **启动免责横幅** — `__main__` 启动时打印醒目法律边界提醒
- 🔥🔥🔥 **安全报告机制** — 新增 `SECURITY.md` 负责任披露政策
- 🔥🔥 **速率限制** — 已有 3 秒间隔 + 50 次上限

**飞书审批链路修复**：
- ReplyServer `PendingRegistry.resolve()` 多实例 reload 修复
- Button `value` 格式修正（对象 → 正确格式）
- `action` 值：`ALLOW`/`DENY`（大写）

**新增文件**：
- `web4_IRON_RULES.md` — Web4.0 铁律完整文档（硬编码版）
- `SECURITY.md` — 安全政策 + 负责任披露流程

## 🔥 v11.8 修复（2026-04-21）
- 重启告警优化：少于5次静默拉起，不刷屏
- task_agent MAX_RUNTIME 2小时→24小时（修复无限重启）
- watcher 新增任务开始时推送通知
- 飞书进度通知链路打通（progress_tracker → watcher → Webhook）

## 🔥 v11 核心功能：飞书审批联动

```
AI 检测到危险操作
  → 自动发送审批卡片到飞书群
  → AI 阻塞等待（wait_for_approval）
  → 坤哥点「✅ 允许放行」按钮
  → 飞书弹出 toast 提示「✅ 允许」
  → ReplyServer 更新注册表
  → wait_for_approval() 返回 True
  → AI 继续执行危险操作
```

**两种审批模式**（见下方 Demo 1 & Demo 2）

## 🏗️ 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    用户对话层                            │
│              (飞书 / Telegram / 群组)                    │
└──────────────────────┬────────────────────────────────┘
                       │
┌──────────────────────▼────────────────────────────────┐
│                   Leader Agent                          │
│  • 理解意图 · 分解任务 · 路由分发 · 质量把控            │
└────┬──────────────┬───────────────┬─────────────────────┘
     │              │               │
┌────▼────┐   ┌────▼────┐    ┌─────▼─────┐
│Researcher│  │ Creator │    │ Engineer │
└──────────┘  └─────────┘    └───────────┘
                       │
        ┌──────────────┴──────────────┐
        │         记忆存储层            │
        │  MEMORY.md · memory/ 日记   │
        └──────────────────────────────┘
```

## 🚀 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/YuchenKuney/openclaw-memory-architecture-public.git
cd openclaw-memory-architecture-public

# 2. 运行 Demo
python3 demo.py --demo ecommerce --scenario  # 电商记忆演进
python3 demo.py --demo 1                      # Demo 1：长连接审批
python3 demo.py --demo 2                      # Demo 2：回调地址审批
```

### 环境变量配置（可选）

```bash
# 飞书企业自建应用（用于审批联动）
export FEISHU_APP_ID="cli_xxxx"
export FEISHU_APP_SECRET="xxxx"
export FEISHU_VERIFICATION_TOKEN="xxxx"
export FEISHU_GROUP_ID="oc_xxxx"
```

## 📦 核心模块

### 记忆层（scripts/）

| 文件 | 作用 |
|------|------|
| `progress_tracker.py` | 飞书进度卡片（方案A主动汇报）|
| `task_monitor.py` | 任务监控 + 看门狗 |
| `task_watchdog.py` | 子 agent 掉线自动拉起 |

### 安全审计（clawkeeper/）

| 文件 | 作用 |
|------|------|
| `detector.py` | 正则 + LLM 语义双层风险检测 |
| `interceptor.py` | 四级分层响应 + 沙箱隔离 |
| `reply_handler.py` | **ReplyServer：接收飞书卡片回调** |
| `notifier.py` | 飞书卡片通知 |
| `notifier.py` | **StepReporter：AI 每步主动汇报（全链路透明化）** |
| `auditor.py` | 主动扫描（CVE/完整性）|
| `knowledge_graph.py` | 实体知识图谱 |
| `context_builder.py` | 上下文构建 |

### Demo 场景系统（demo/）

| 文件 | 作用 |
|------|------|
| `demo.py` | 统一入口 |
| `demo/scenarios/ecommerce.py` | 电商记忆演进场景 |
| `demo/engine/runner.py` | 场景运行器 |
| `demo1_longpoll.py` | **Demo 1：长连接审批** |
| `demo2_callback.py` | **Demo 2：回调地址审批** |

### Web4.0 AI 视觉（根目录）

| 文件 | 作用 |
|------|------|
| `web4_browser.py` | Playwright 无头浏览器 + **17项 stealth 反检测** |
| `web4_container.py` | Linux Namespace 沙箱容器 |
| `web4_controller.py` | AI 研究接口 |
| `web4_cooker.py` | Cooking 注入引擎 |

**Stealth 措施**：移除 navigator.webdriver、Chrome 运行时伪装、Plugins/MimeTypes 仿真、Canvas 指纹加噪、WebGL 渲染器伪装、HardwareConcurrency 仿真等。实测 Bing 搜索从 0 结果→34,600 条真实数据。

## 🎯 Demo 审批系统详解

### Demo 1：长连接审批模式

**原理**：OpenClaw 每5秒轮询飞书群消息，检测 `@审批机器人` + 文字命令

**优点**：简单（只需读取消息权限），无需公网地址
**缺点**：有5秒轮询延迟

```
坤哥操作：
1. 运行 python3 demo.py --demo 1
2. 群里收到文字审批卡片
3. @审批机器人 + 发送「允许」
4. 监听器收到命令，wait_for_approval() 放行
```

### Demo 2：回调地址审批模式

**原理**：公网 HTTP 服务器（ReplyServer）接收飞书卡片按钮回调，实时弹窗

**优点**：卡片按钮 + toast 弹窗 + 实时响应
**缺点**：需公网地址 + 飞书事件订阅配置

```
坤哥操作：
1. 运行 python3 demo.py --demo 2
2. 群里收到带按钮的审批卡片
3. 点击「✅ 允许放行」按钮
4. 飞书弹出 toast「✅ 允许」
5. ReplyServer 更新注册表，wait_for_approval() 放行
```

### 核心类：wait_for_approval()

```python
# Demo 1 & Demo 2 都实现了 wait_for_approval()
# AI 执行危险操作前必须调用此方法阻塞等待审批

result = wait_for_approval(
    action_id="high-xxx",
    message="[HIGH] 删除文件 /tmp/test.txt",
    level="HIGH",
    timeout=300
)

if result:
    # 坤哥点了「允许」→ AI 继续执行
    os.remove("/tmp/test.txt")
else:
    # 坤哥点了「拒绝」或超时 → AI 阻断
    print("❌ 审批拒绝，操作已取消")
```

### ReplyServer 回调格式

**飞书 → ReplyServer（POST /feishu/reply）**：
```json
{
  "schema": "2.0",
  "header": {
    "event_type": "card.action.trigger",
    "token": "8KzbQpgFADOEM1n6J2Bm3cNw7Rf7MPMk"
  },
  "event": {
    "operator": {"name": "坤哥", "open_id": "ou_xxx"},
    "action": {
      "tag": "button",
      "value": {
        "approval_id": "high-xxx",
        "action": "ALLOW",
        "risk_level": "HIGH"
      }
    }
  }
}
```

**ReplyServer → 飞书（200 OK）**：
```json
{
  "status_code": 0,
  "status_msg": "success",
  "data": {"template_variable": {"status": "✅ 允许"}},
  "toast": {"type": "success", "content": "✅ 允许"}
}
```

## 🛡️ 反黑箱安全审计

> **核心理念**：AI 的每一个操作都对用户可见，坤哥始终知道 AI 在做什么

### 风险等级与响应

| 等级 | 操作示例 | 响应方式 |
|------|---------|---------|
| 🔴 CRITICAL | 删除核心文件（AGENTS.md/MEMORY.md）| **立即拦截 + 立即通知** |
| 🚨 HIGH | 修改核心目录、危险系统操作 | **沙箱隔离 + 飞书卡片审批** |
| ⚠️ MEDIUM | push 到公共仓库 | **沙箱隔离 + 飞书卡片审批** |
| 📝 LOW | 创建普通文件 | **沙箱隔离 + 飞书卡片审批** |
| ✅ SAFE | 正常操作 | 放行 |

### 审批卡片示例

```
🚨 审批请求 [HIGH]

🤖 操作: [HIGH] 删除文件 /tmp/test.txt
🆔 审批ID: high-xxx

[✅ 允许放行]  [❌ 拒绝]
```

### 拦截响应流程

```
危险操作检测
  → interceptor.py 拦截
  → 写入 pending_actions.json（status=pending）
  → 发送飞书审批卡片
  → wait_for_approval() 阻塞
  → 坤哥点按钮 → ReplyServer 更新 registry
  → wait_for_approval() 返回
  → ALLOW: AI 继续执行
  → DENY/超时: AI 阻断
```

### 透明化铁律

| 要求 | 说明 |
|------|------|
| **分阶段报告** | 接到任务先说"分 X 步"，每步完成后主动报告 |
| **说多久是多久** | "预计30秒"就是30秒 |
| **主动交付** | 完成后立即发送，不等用户问 |
| **状态明确** | 不用"等待中"，用 `waiting_for_input/tool/subtask` |

## 🔄 版本演进

| 版本 | 核心改进 |
|------|---------|
| v1-v4 | 基础记忆 CRUD |
| v5 | 多智能体协作层 + 冲突检测 |
| v6 | 图检索 + 反思引擎 |
| **v7** | **主动进度反馈 + 任务状态结构化** |
| **v8** | **反黑箱安全审计（AI行为全透明 + inotify监控 + 风险分级）** |
| **v9** | **Web4.0 AI Agent 沙箱无头浏览器 + Cooking 注入引擎** |
| **v10** | **反黑箱通知铁律落地 + 看门狗自动拉起子 agent** |
| **v11.7** | **StepReporter 全链路透明化 + Web4.0 stealth 加强（Bing 搜索突破）** |
| **v11.6** | **飞书审批联动：卡片按钮 + toast 弹窗 + wait_for_approval 阻塞** |

## 📁 目录结构

```
openclaw-memory-architecture/
├── demo.py                      # Demo 统一入口
├── demo/
│   ├── scenarios/ecommerce.py   # 电商记忆演进场景
│   ├── engine/runner.py         # 场景运行器
│   ├── demo1_longpoll.py       # Demo 1：长连接审批
│   └── demo2_callback.py       # Demo 2：回调地址审批
├── clawkeeper/                  # 安全审计
│   ├── detector.py             # 风险检测
│   ├── interceptor.py           # 拦截器 + 沙箱
│   ├── reply_handler.py        # ReplyServer 回调处理
│   ├── notifier.py             # 飞书通知
│   ├── feishu_api.py           # 飞书 API
│   ├── auditor.py              # 审计报告
│   └── watcher.py              # inotify 监控
├── scripts/
│   ├── progress_tracker.py      # 飞书进度卡片
│   ├── task_monitor.py          # 任务监控
│   └── task_watchdog.py        # 看门狗
├── web4_*.py                   # Web4.0 视觉模块
├── memory/                      # 日记层
│   └── YYYY-MM-DD.md
├── memory/                      # 日记层
├── AGENTS.md                   # Agent 操作规范
├── ANTI_BLACKBOX.md            # 反黑箱文档
├── web4_IRON_RULES.md         # Web4.0 铁律（硬编码版）
└── SECURITY.md                # 安全政策 + 负责任披露
```

## 🌐 Web4.0 AI Agent 沙箱

> **给 AI 装一双眼睛** — AI 在沙箱隔离环境中自主浏览网页、分析研究

### Cooking 预设

| 预设 | 语言 | 策略 | 适用场景 |
|------|------|------|---------|
| `中文优先` | zh | standard | 中文资讯 |
| `学术研究` | en | deep | arXiv / Nature |
| `快速扫描` | any | brief | 快速摸底 |
| `技术深度` | en | deep | 深度技术分析 |

### 隔离安全特性

- **Namespace 隔离**：PID / Network / Mount / IPC / UTS / User
- **Seccomp 过滤**：只允许 ~100 个安全系统调用
- **IPv6 ULA**：每容器分配唯一地址
- **Cookie 铁律**：只注入 Google preference cookies，禁止登录态 tokens
- **robots.txt 合规**：铁律五，fetch_page 集成检查
- **审计日志**：铁律六，IronRuler.audit_log() 全量记录

## 🤝 贡献与支持者

欢迎提交 **Issue** 和 **Pull Request**！

有效 Issue 被采纳后可加入 [CONTRIBUTORS.md](CONTRIBUTORS.md) 支持者名单。

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)
