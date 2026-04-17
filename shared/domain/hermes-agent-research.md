# Hermes Agent 学习笔记
*学习日期：2026-04-16*

## 项目信息
- **来源**：NousResearch (https://github.com/NousResearch/hermes-agent)
- **定位**：自我改进的 AI 智能体，内置学习循环
- **特点**：与 OpenClaw 高度相似，有迁移工具（hermes claw migrate）

## 核心架构

### 记忆系统（Memory）
**结构：**
- `MEMORY.md` — 智能体笔记（2,200 字符，约 800 tokens）
- `USER.md` — 用户画像（1,375 字符，约 500 tokens）
- 存储位置：`~/.hermes/memories/`

**关键设计：**
1. **Frozen Snapshot Pattern** — 记忆在会话开始时注入，会话期间不变
2. **Memory Tool** — add / replace / remove（无 read，自动注入）
3. **字符限制** — 严格限制保持 system prompt 有界
4. **Session Search** — FTS5 全文搜索所有历史会话
5. **外部记忆提供者** — 8 个插件（Honcho, Mem0, OpenViking 等）

**容量管理：**
- 80% 以上时应该合并/精简条目
- 满时返回错误，要求先清理再添加

### 技能系统（Skills）
**结构：**
- `SKILL.md` 格式标准化
- 支持 metadata、platforms、config settings
- 渐进式加载（3 级）：
  - Level 0: skills_list() → name, description, category (~3k tokens)
  - Level 1: skill_view(name) → 完整内容
  - Level 2: skill_view(name, path) → 特定参考文件

**条件激活：**
```yaml
metadata:
  hermes:
    fallback_for_toolsets: [web]  # 当 web 工具集不可用时显示
    requires_toolsets: [terminal]  # 当 terminal 工具集可用时显示
```

**智能体自主创建技能触发条件：**
- 完成复杂任务（5+ tool calls）后
- 遇到错误并找到解决方案后
- 用户纠正其方法后

### 代理循环（Agent Loop）
**核心组件：**
- `AIAgent` (run_agent.py) — 核心对话循环
- `PromptBuilder` — 系统提示构建
- `ProviderResolution` — 模型提供者选择
- `ToolDispatch` — 工具注册表（47 工具，19 工具集）

**数据流：**
```
User input → HermesCLI.process_input()
  → AIAgent.run_conversation()
  → prompt_builder.build_system_prompt()
  → runtime_provider.resolve_runtime_provider()
  → API call
  → tool_calls? → model_tools.handle_function_call() → loop
  → final response → display → save to SessionDB
```

### Cron 调度
- 内置 cron 调度器
- 自然语言配置定时任务
- 支持投递到任意平台

### 平台支持
- **18 个消息平台适配器**：Telegram, Discord, Slack, WhatsApp, Signal, Matrix, Email 等
- **6 个终端后端**：local, Docker, SSH, Daytona, Singularity, Modal

## 可借鉴的设计

### 1. 记忆容量硬限制
Hermes 有严格的字符限制，强制智能体在满时先精简再添加。
**借鉴：** 我的当前系统没有硬限制，可以考虑加入类似机制。

### 2. 技能渐进式加载
技能不需要全部加载，只在需要时加载完整内容。
**借鉴：** 适用于复杂技能，可以分层加载基础/进阶内容。

### 3. 外部记忆提供者
支持第三方记忆系统插件。
**借鉴：** 我的架构已支持，但可以扩展支持的外部提供者。

### 4. 技能条件激活
根据可用工具自动显示/隐藏技能（fallback 技能）。
**借鉴：** 可以实现"当 X 工具不可用时自动使用 Y 技能"的逻辑。

### 5. 智能体自主创建技能
智能体可以自己判断是否需要将工作流保存为技能。
**借鉴：** OpenClaw 的 skill-creator 技能可以做类似的事。

## 相似之处
- 都是多平台 AI 智能体（Telegram, Discord, Slack 等）
- 都支持技能系统
- 都支持记忆持久化
- 都有 cron 调度功能
- 都支持多种模型提供者
- 都支持 MCP (Model Context Protocol)

## 主要差异
| 特性 | Hermes | OpenClaw |
|------|--------|----------|
| 记忆系统 | 严格字符限制 | SQLite + Markdown |
| 技能创建 | 智能体自动创建 | 手动创建 |
| 工具数量 | 47 工具 | 较少 |
| 平台适配 | 18 个 | 类似 |
| 上下文压缩 | 自动摘要 | 依赖模型 |

## 文档链接
- 主站：https://hermes-agent.nousresearch.com/docs/
- GitHub：https://github.com/NousResearch/hermes-agent