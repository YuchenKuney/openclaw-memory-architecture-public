# 反黑箱文档 / Anti-Blackbox Operation

> "坤哥要求：AI 执行任务的每一步都对坤哥可见"
> "全链路透明化执行铁律：每一步都要说出来，不做静默执行"

---

## 📌 目录

1. [概念说明](#概念说明)
2. [核心模块](#核心模块)
3. [透明度级别](#透明度级别)
4. [工作模式 vs 日常模式](#工作模式-vs-日常模式)
5. [快速开始](#快速开始)
6. [demo.py 一键启动](#demo-py-一键启动)
7. [架构图](#架构图)

---

## 概念说明

### 什么是"反黑箱"？

传统 AI 执行任务时：用户说"帮我审计代码" → AI 内部操作 → 最后只给一个结果，用户完全看不到中间过程。

反黑箱：每个操作步骤都透明可见，坤哥可以实时看到 AI 在做什么、卡在哪里、结果如何。

### 三层透明化

| 层级 | 内容 | 工具 |
|------|------|------|
| **执行层** | AI 每一步操作 | progress_tracker.py → inotify → 飞书 |
| **认知层** | 风险判断依据 | knowledge_graph.py → context_builder |
| **记忆层** | 事件溯源 | memory/ 日记 → KG 实体 |

---

## 核心模块

| 模块 | PR | 职责 |
|------|-----|------|
| `detector.py` | PR① | 正则 + LLM 语义双层风险检测 |
| `interceptor.py` | PR② | 四级分层响应（LOG/WARN/BLOCK/KILL） |
| `auditor.py` | PR③ | 主动扫描（CVE/完整性/Skill模式） |
| `watcher.py` | - | inotify 文件监控 |
| `notifier.py` | - | 飞书卡片通知 |
| `knowledge_graph.py` | PR④ | 实体知识图谱 + 三层记忆联动 |
| `context_builder.py` | PR④ | 上下文构建（整合三层记忆） |
| `demo.py` | PR⑤ | 一键启动演示脚本 |

---

## 透明度级别

### 四级分层响应

```
CRITICAL 🔴 (CRITICAL = 4)
├── KILL_AND_ISOLATE
├── 收集取证数据（进程快照 + audit.log + 上下文）
├── 系统暂停（CLAWKEEPER_PAUSED=1）
└── 飞书最高级别告警卡片

HIGH 🚨 (HIGH = 3)
├── BLOCK_AND_NOTIFY
├── 系统暂停（CLAWKEEPER_PAUSED=1）
├── 等待坤哥审批
└── 飞书紧急通知

MEDIUM ⚠️ (MEDIUM = 2)
├── WARN_AND_LOG
├── 飞书警告通知
└── AI 可继续执行

LOW 📝 (LOW = 1) / SAFE ✅ (SAFE = 0)
├── LOG_ONLY
├── 只写日志，不通知
└── AI 正常执行
```

### 实时进度透明化

```
Cron 触发（精确到秒）
  → agentTurn 执行，写入 cron-events/{id}.json
  → inotify 毫秒级感知
  → clawkeeper 解析 JSON
  → progress_tracker.py 写入 tasks/progress/{job_id}.json
  → inotify 再次感知 progress 文件
  → 飞书卡片推送坤哥
  → 坤哥在飞书看到完整事件
```

---

## 工作模式 vs 日常模式

| 模式 | 触发条件 | 响应 |
|------|---------|------|
| **工作模式** | 包含 `帮我`/`执行`/`audit`/`fix`/`push` 等 | 完整四层响应，严格拦截 |
| **日常模式** | 纯问候/闲聊（`你好`/`谢谢`/`?`） | 降级处理（CRITICAL→MEDIUM，HIGH→LOW） |

意图分类器（`IntentClassifier`）自动区分：

```python
# 工作模式
"帮我修一下 bug" → work 模式 → 严格检测

# 日常模式
"你好，今天天气怎么样" → chat 模式 → 降级放行
```

---

## 快速开始

### 方式一：demo.py 交互式启动（推荐）

```bash
cd /root/.openclaw/workspace
python3 demo.py
```

会依次提示：
1. 检查依赖（Python 3 / inotify）
2. 输入飞书 Webhook URL（首次配置需要）
3. 输入飞书群 ID
4. 显示透明化 cron 任务状态
5. 填充知识图谱
6. 启动 Clawkeeper

### 方式二：命令行参数

```bash
# 只检查依赖
python3 demo.py --check

# 指定配置
python3 demo.py --webhook "https://open.feishu.cn/open-apis/bot/v2/hook/xxxx" \
                --group "oc_0533b03e077fedca255c4d2c6717deea"

# 只填充知识图谱
python3 demo.py --populate

# 查看项目信息
python3 demo.py --info
```

### 方式三：查看 PR①-⑤ 详细说明

```bash
# 查看所有测试（验证各模块正常工作）
cd /root/.openclaw/workspace
python3 -m unittest tests.test_detector tests.test_interceptor \
         tests.test_auditor tests.test_knowledge_graph -v

# 查看知识图谱
python3 knowledge_graph.py --show

# 从 memory/ 填充实体
python3 knowledge_graph.py --populate

# 主动扫描
python3 -c "
import sys; sys.path.insert(0, '.')
from clawkeeper.auditor import Auditor
a = Auditor()
result = a.active_scan()
print(a.format_scan_report(result))
"
```

---

## demo.py 一键启动

`demo.py` 是 Clawkeeper 的演示启动脚本，提供交互式配置和一键启动。

### 首次使用

```bash
$ python3 demo.py

  ╔══════════════════════════════════════════╗
  ║   Clawkeeper  反黑箱安全监控系统  v2.0   ║
  ╚══════════════════════════════════════════╝

  全链路透明化 · 四级分层响应 · 三层记忆联动

  [1] 依赖检查...
  [2] 飞书配置...
  [3] 透明化 Cron 任务...
  [4] 知识图谱填充...
  [5] Clawkeeper 启动...

  首次配置需要设置飞书机器人信息

  ──────────────────────────────────────────────────
  📡 飞书 Webhook URL
  请输入 webhook 地址，例如：
  https://open.feishu.cn/open-apis/bot/v2/hook/xxxx
  输入 webhook（直接回车跳过）: https://open.feishu.cn/...
  👥 飞书群 ID
  输入群 ID（直接回车跳过）: oc_0533b03e077fedca255c4d2c6717deea
```

### 输出示例

```
============================================================
  启动完成
============================================================
  ✅ Clawkeeper 已就绪，所有事件将透明化通知到飞书群
```

### 配置保存

demo.py 会将配置保存到 `clawkeeper/config.yaml`：
```yaml
webhook: "https://open.feishu.cn/open-apis/bot/v2/hook/7a939580-..."
group_id: "oc_0533b03e077fedca255c4d2c6717deea"
```

---

## 架构图

```
┌─────────────────────────────────────────────────────────┐
│                   Clawkeeper 系统                        │
│                  反黑箱安全监控系统                       │
└─────────────────────────────────────────────────────────┘
                          │
    ┌─────────────────────┼─────────────────────┐
    ↓                     ↓                     ↓
┌─────────┐       ┌──────────────┐       ┌─────────────┐
│ Watcher │ ────▶ │  Detector   │ ────▶ │ Interceptor │
│ inotify │       │ PR① 双层    │       │ PR② 四级    │
│ 文件监控│       │ 正则+LLM    │       │ 分层响应    │
└─────────┘       └──────────────┘       └─────────────┘
    │                    │                    │
    │                    │                    ▼
    │                    │            ┌──────────────┐
    │                    │            │  Notifier   │
    │                    │            │  飞书卡片    │
    │                    │            └──────────────┘
    │                    │
    │                    ▼
    │            ┌──────────────┐
    │            │ Auditor      │
    │            │ PR③ 主动扫描│
    │            └──────────────┘
    │
    └──────────────┐
                    │ 感知层事件
                    ▼
          ┌──────────────────────┐
          │   Knowledge Graph    │
          │   PR④ 三层记忆联动   │
          └──────────────────────┘
                    │ 认知层实体
                    ▼
          ┌──────────────────────┐
          │   Context Builder    │
          │   PR④ 三层记忆联动   │
          └──────────────────────┘

─── 透明化事件流 ──────────────────────────────────────────

文件事件 ──▶ inotify ──▶ progress_tracker.py
                           │
                           ▼ inotify 毫秒感知
                      clawkeeper
                           │
                           ▼
               飞书群卡片推送（坤哥实时可见）
```

---

## PR⑥ 动态用户画像

### 核心理念

传统安全系统：所有用户一刀切，新用户和老专家用同一套规则。

反黑箱动态调整：根据用户画像动态调整风险等级。

### 三层记忆联动

```
memory/ 日记文件
    ↓ 日志蒸馏（distill_from_memory）
用户画像（.user_profile.json）
    ↓ 动态调整（get_adjusted_risk）
detector.py 风险评估
    ↓
最终风险等级
```

### 用户画像内容

| 字段 | 说明 |
|------|------|
| `familiarity` | 各命令/技术的熟悉度（0.0-1.0） |
| `risk_tolerance` | 风险容忍度（low/normal/high） |
| `capabilities` | 推断的能力列表 |
| `learning_notes` | 从 memory/ 日记中学到的笔记 |
| `recent_commands` | 最近 50 条操作记录 |
| `total_events` | 总事件数 |

### 熟悉度阈值

- **≥ 60%**：命令被标记为"熟悉"，HIGH 自动降为 MEDIUM
- **< 60%**：新用户首次操作，LOW 可能升为 MEDIUM（加强观测）
- **多种工具使用**（≥3种）：风险容忍度自动提升到 "high"

### 命令熟悉度表

| 命令 | 初始等级 | 说明 |
|------|---------|------|
| git | HIGH | 仓库操作 |
| npm/pip | HIGH | 包管理 |
| docker | HIGH | 容器操作 |
| subprocess/eval/exec | HIGH | 代码执行 |
| curl | MEDIUM | 网络请求 |
| chmod | MEDIUM | 权限修改 |

### 示例场景

**场景1：新用户第一次用 git**
```
输入: git push
base_risk: HIGH
adjusted: HIGH（保持，因为不熟悉）
reason: "新用户首次操作 [git]，提高观测级别"
```

**场景2：用户已熟悉 docker**
```
输入: docker build
base_risk: HIGH
adjusted: MEDIUM（熟悉度 75% ≥ 60%）
reason: "用户已熟悉 [docker]（熟悉度75%），自动降级"
```

**场景3：从 memory/ 日记发现用户开始用 git**
```
memory/2026-04-19.md: "今天完成了 git push 操作"
    ↓ distill_from_memory()
familiarity["git"] += 0.3
learning_notes.append("2026-04-19.md: 发现 git 使用")
    ↓ 下次 git 操作
adjusted: MEDIUM（已熟悉，自动降级）
```


### 查看用户画像

```bash
# 查看当前画像
python3 clawkeeper/user_profile.py --show

# 从 memory/ 蒸馏更新画像
python3 clawkeeper/user_profile.py --distill

# 记录一条操作
python3 clawkeeper/user_profile.py --record "git push" EXEC /workspace

# 检查命令熟悉度
python3 clawkeeper/user_profile.py --check "git"
```

### 画像输出示例

```
用户画像 v1.0
创建时间: 2026-04-19 15:00:00
总事件数: 47
风险容忍度: high

命令熟悉度:
  git         [████████░░] 80% 🟢 熟悉
  docker      [██████░░░░] 65% 🟢 熟悉
  npm         [███░░░░░░░] 30% 🔵 学习
  curl        [████░░░░░░] 40% 🔵 学习

能力: 版本控制, 容器化, DevOps, Python开发

最近学习:
  • 2026-04-19.md: 发现 git 使用
  • 2026-04-19.md: 用户使用了 subprocess.run（已熟悉，降级风险）
```

---

## Task Monitor + Task Watchdog（子 agent 主动监控）

### 核心理念

子 agent 实时监控主 agent 任务进度，主动推送飞书卡片，watchdog 守护子 agent 不挂。

### 三进程架构

```
主 agent（坤哥的 AI）
    ↓ 写入 progress tracker
tasks/progress/current_task.json
    ↓
子 agent（task_monitor.py）
    → 检测进度变化 → 主动飞书推送
    → 任务完成 → 推送完成卡片
    ↓ 守护
看门狗（task_watchdog.py）
    → 监控子 agent 进程
    → 挂了自动拉起
    → 每 30 秒飞书心跳
    → 每 5 分钟 memory 完整性检查
```

### 进程职责

| 进程 | 文件 | 职责 |
|------|------|------|
| 主 agent | OpenClaw | 执行任务，写入 progress |
| 子 agent | `task_monitor.py` | 实时监控进度，主动推送飞书 |
| 看门狗 | `task_watchdog.py` | 守护子 agent 不挂 |

### 进度推送流程

```
主 agent 任务进行中
    ↓ 每步写入
tasks/progress/current_task.json  {"name", "progress", "step", "status"}
    ↓ 每 3 秒轮询
task_monitor.py 子 agent
    ↓ 进度变化时主动推送
飞书群卡片（实时）
    ↓
坤哥在飞书看到完整进度
```

### task_monitor.py 功能

```bash
python3 task_monitor.py          # 前台运行
# 推送内容：
#   🚀 任务启动卡片
#   📊 实时进度卡片（每步变化）
#   ✅ 任务完成卡片
#   ❌ 任务错误卡片
```

### task_watchdog.py 功能

```bash
python3 task_watchdog.py --daemon   # 后台常驻
python3 task_watchdog.py --once     # 单次检测（调试）


# 守护内容：
#   - 子 agent 进程存活检测（每 5 秒）
#   - 进程挂了自动拉起
#   - 每 30 秒飞书心跳
#   - 每 5 分钟 memory 完整性校验
```

### 推送卡片示例

**启动：**
```
🚀 {task_name} 已启动

📋 共 N 个步骤
🔄 子 agent 监控中，进度将实时推送...
```

**进度更新：**
```
{task_name}
🔄 [████████░░] 80%
📍 当前: Step 3/4 - 执行代码
```

**完成：**
```
✅ 任务完成

{task_name}

📍 最终状态: 已推送到 GitHub
```


### 启动方式

**方式一：看门狗自动守护**
```bash
python3 task_watchdog.py --daemon
# 自动启动 monitor，自动拉起挂了的服务
```

**方式二：手动启动 monitor**
```bash
python3 task_monitor.py
# 配合 watchdog 使用
```


**方式三：OpenClaw subagent**
```bash
# 在 OpenClaw 中启动子 agent
openclaw tasks spawn --runtime=subagent --task-file task_monitor.py
```

---

_Last updated: 2026-04-19_
