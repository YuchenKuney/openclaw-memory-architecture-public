# 2026年3月 GitHub AI Agent 项目热门调研报告

> 调研时间：2026年4月23日  
> 数据来源：GitHub Trending（Monthly）、GitHub Search、行业媒体

---

## 📊 执行摘要

2026年3月，AI Agent 开源生态迎来爆发式增长。GitHub 月度 trending 中 AI Agent 相关项目占据主导地位，明星项目单月 stars 突破 10 万。本报告按**基础设施 / 框架 / 应用 / 研究**四大分类整理，并给出选品建议。

---

## 🏗️ 一、基础设施类 TOP 5

### 1️⃣ OpenAI Agents SDK ⭐ 超高热度
- **仓库**: [openai/openai-agents-python](https://github.com/openai/openai-agents-python)
- **语言**: Python
- **特色**: OpenAI 官方出品的轻量级多 Agent 框架，支持 100+ LLM 提供商
- **核心能力**:
  - Agents / Sandbox Agents / Handoffs（Agent 间协作）
  - MCP (Model Context Protocol) 工具集成
  - Guardrails（输入输出安全校验）
  - Human-in-the-loop
  - Realtime Agents（语音模式）
- **适用场景**: 需要快速构建多 Agent 协作系统，且使用 OpenAI 或兼容 API 的团队

### 2️⃣ LangGraph ⭐ 图形化 Agent 构建
- **仓库**: [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph)
- **语言**: Python
- **特色**: 将 Agent 建模为图结构，支持持久化执行、人机交互、长期记忆
- **核心能力**:
  - Durable Execution（容错恢复）
  - Human-in-the-loop（状态检查/修改）
  - 短/长期记忆管理
  - LangSmith 可视化调试
  - 与 LangChain 生态深度集成
- **适用场景**: 需要构建复杂、长时间运行、有状态工作流的 Agent 系统

### 3️⃣ Mastra ⭐ TypeScript 现代栈
- **仓库**: [mastra-ai/mastra](https://github.com/mastra-ai/mastra)
- **语言**: TypeScript/Node.js
- **特色**: Gatsby 团队出品，面向 TypeScript 开发者的 AI 应用框架
- **核心能力**:
  - 40+ 模型路由
  - 工作流引擎（.then() / .branch() / .parallel()）
  - Human-in-the-loop（暂停/恢复）
  - MCP Server 创作
  - 内置 Eval 和可观测性
  - 与 React/Next.js 无缝集成
- **适用场景**: TypeScript 团队，React/Next.js 技术栈，需要快速交付生产级 Agent

### 4️⃣ Microsoft Agent Framework ⭐ 企业级
- **仓库**: [microsoft/agent-framework](https://github.com/microsoft/agent-framework)
- **语言**: Python
- **特色**: Microsoft 企业级多 Agent 编排框架，AutoGen 的官方继任者
- **核心能力**:
  - 企业级多 Agent 编排
  - 多提供商模型支持
  - A2A 和 MCP 跨运行时互操作
  - 长期支持保障
- **适用场景**: 企业级生产部署，需要稳定支持和长期维护的项目

### 5️⃣ DB-GPT（数据 Agent）⭐ 垂直领域
- **仓库**: [eosphoros-ai/DB-GPT](https://github.com/eosphoros-ai/DB-GPT)
- **语言**: Python
- **特色**: 开源 AI 数据助手，连接数据库、文件、仓库，自然语言生成 SQL
- **核心能力**:
  - 自然语言 SQL 生成
  - 代码驱动分析流程
  - 可视化图表/仪表盘生成
  - 沙箱安全执行
  - 多模型支持
- **适用场景**: 数据分析团队，需要 AI 辅助 SQL 查询和报告生成

---

## 🔧 二、框架类 TOP 5

### 1️⃣ NousResearch/hermes-agent ⭐⭐⭐ 3月最大黑马
- **仓库**: [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- **语言**: Python
- **总 Stars**: 110,679 | **本月新增**: 100,638
- **特色**: 自改进 AI Agent，内置学习循环——从经验中创建技能、使用中自我优化
- **核心能力**:
  - Agent 自进化（经验 → 技能创建 → 持续改进）
  - 多渠道接入：Telegram / Discord / Slack / WhatsApp / Signal / Email
  - 40+ 内置工具
  - 多模型支持（OpenRouter 200+、OpenAI、Anthropic、HuggingFace 等）
  - Cron 定时任务（自然语言定义）
  - 多终端后端：本地 / Docker / SSH / Daytona / Modal
  - MCP 集成
  - 研究级功能：批量轨迹生成、Atropos RL
- **安装**: `curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash`
- **适用场景**: 需要个人 AI 助手、跨平台工作流自动化、科研轨迹收集

### 2️⃣ affaan-m/everything-claude-code ⭐⭐⭐ Anthropic Hackathon 冠军
- **仓库**: [affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code)
- **语言**: JavaScript / Python
- **总 Stars**: 164,250 | **本月新增**: 69,085 | Forks: 25,492
- **特色**: Claude Code / Codex / Cursor / OpenCode 性能优化系统
- **核心能力**:
  - Token 优化（模型选择、系统提示精简）
  - 记忆持久化（Hook 自动保存/加载上下文）
  - 持续学习（从会话中自动提取模式为可复用技能）
  - 验证循环（Checkpoint eval、Pass@k）
  - 并行化（Git worktrees、Cascade 方法）
  - 子 Agent 编排
  - AgentShield 安全扫描
  - Tkinter Dashboard GUI
  - ECC 2.0 (Rust 控制平面 alpha)
- **适用场景**: 深度使用 Claude Code 等编码 Agent 的开发者，追求极致性能

### 3️⃣ LangChain（LangChain Agents）⭐ 生态最全
- **仓库**: [langchain-ai/langchain](https://github.com/langchain-ai/langchain)
- **语言**: Python / JavaScript
- **特色**: 最完整的 LLM 应用生态，支持多种 Agent 类型和工具集成
- **Agent 类型**: ReAct、Plan-and-Execute、Self-ask、Tool-calling 等
- **适用场景**: 需要丰富工具生态、快速原型、LangSmith 可观测性

### 4️⃣ Archon ⭐ AI Coding 工作流引擎
- **仓库**: [coleam00/Archon](https://github.com/coleam00/Archon)
- **语言**: TypeScript
- **总 Stars**: 19,362 | **本月新增**: 5,672
- **特色**: 首个开源 AI Coding Harness 构建器，用 YAML 定义开发流程
- **核心能力**:
  - YAML 定义开发流程（Plan → Implement → Validate → Review → PR）
  - 确定性执行（每次运行结果一致）
  - 隔离性（每个运行使用独立 Git worktree）
  - 混用确定性节点（bash/test）和 AI 节点
  - 支持 CLI / Web UI / Slack / Telegram
- **类比**: "Dockerfile 做基础设施，GitHub Actions 做 CI/CD，Archon 做 AI Coding"
- **适用场景**: 团队需要标准化 AI 编码流程，追求可重复的 AI 开发体验

### 5️⃣ CrewAI ⭐ 角色扮演多 Agent
- **仓库**: [crewAI/CrewAI](https://github.com/crewAI/CrewAI)
- **语言**: Python
- **特色**: 通过角色扮演和协作智能编排多 Agent，模拟真实组织结构
- **核心概念**: Agents（角色）、Tasks（任务）、Tools（工具）、Crews（团队）
- **适用场景**: 需要多角色协作流程（研究员 + 分析师 + 执行者等）

---

## 🎯 三、应用类 TOP 5

### 1️⃣ forrestchang/andrej-karpathy-skills ⭐ Claude Code 技能增强
- **仓库**: [forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills)
- **语言**: Markdown（CLAUDE.md）
- **总 Stars**: 76,206 | **本月新增**: 67,820 | Forks: 7,094
- **特色**: 基于 Andrej Karpathy 对 LLM 编码缺陷的观察，优化的 Claude Code 配置
- **内容**: 单个 CLAUDE.md 文件，即插即用，直接提升 Claude Code 行为质量
- **适用场景**: 所有 Claude Code 用户，快速提升编码质量

### 2️⃣ mvanhorn/last30days-skill ⭐ AI 研究 Agent
- **仓库**: [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill)
- **语言**: Python
- **总 Stars**: 23,537 | **本月新增**: 19,158
- **特色**: 跨平台研究 Agent，覆盖 Reddit / X / YouTube / HN / Polymarket / Web
- **输出**: 深度综合分析报告，有据可查
- **适用场景**: 市场调研、竞品分析、舆情监测

### 3️⃣ onyx-dot-app/onyx ⭐ 开源 AI 平台
- **仓库**: [onyx-dot-app/onyx](https://github.com/onyx-dot-app/onyx)
- **语言**: Python
- **总 Stars**: 28,082 | **本月新增**: 10,189
- **特色**: 功能丰富的开源 AI 平台，支持 RAG / Deep Research / 自定义 Agent
- **核心能力**:
  - Agentic RAG（混合索引 + AI Agent）
  - Deep Research（多步研究流程，2026年2月领先）
  - 50+ Connector（Google Drive / Notion / Slack 等）
  - 代码执行（沙箱）
  - 语音模式 / 图像生成
  - MCP 支持
  - 企业功能：SSO / RBAC / SCIM / Analytics
- **一键安装**: `curl -fsSL https://onyx.app/install_onyx.sh | bash`
- **适用场景**: 企业内部 AI 平台搭建，需要 Deep Research 能力

### 4️⃣ Donchitos/Claude-Code-Game-Studios ⭐ 游戏开发多 Agent 系统
- **仓库**: [Donchitos/Claude-Code-Game-Studios](https://github.com/Donchitos/Claude-Code-Game-Studios)
- **语言**: Shell / Claude Code 技能
- **总 Stars**: 15,424 | **本月新增**: 13,770
- **特色**: 将 Claude Code 变成完整游戏工作室——49 个 AI Agent + 72 个工作流技能
- **架构**: 模拟真实工作室层级（CEO → CTO → Art Director → QA 等）
- **适用场景**: 游戏开发者，想用 AI 全流程开发游戏

### 5️⃣ Google Agents（MCP Servers）⭐ Google 官方 Agent 工具
- **仓库**: [google-ai-edge/gallery](https://github.com/google-ai-edge/gallery)（4,800+ 星星）、[google-ai-edge/LiteRT-LM](https://github.com/google-ai-edge/LiteRT-LM)
- **语言**: Kotlin / C++
- **特色**: Google 端侧 ML/GenAI 用例展示，支持本地运行模型
- **适用场景**: 需要 Google 生态集成（Gemini / Material UI / Firebase）的 Agent 开发

---

## 🔬 四、研究类 TOP 5

### 1️⃣ shiyu-coder/Kronos ⭐ 金融市场基础模型
- **仓库**: [shiyu-coder/Kronos](https://github.com/shiyu-coder/Kronos)
- **语言**: Python
- **总 Stars**: 20,298 | **本月新增**: 9,037
- **特色**: 金融市场语言基础模型，专注金融领域理解和推理
- **适用场景**: 金融量化、AI 投研、FinTech 应用

### 2️⃣ HKUDS/DeepTutor ⭐ 个性化 AI 学习助手
- **仓库**: [HKUDS/DeepTutor](https://github.com/HKUDS/DeepTutor)
- **语言**: Python
- **总 Stars**: 21,015 | **本月新增**: 10,276
- **特色**: Agent 原生个性化学习助手，深度理解学习者需求
- **适用场景**: 教育科技、在线学习平台、自适应教学系统

### 3️⃣ Deep Agents（LangChain）⭐ Agent 构建库
- **仓库**: [langchain-ai/deepagents](https://github.com/langchain-ai/deepagents)
- **特色**: LangChain 新推出的 Agent 构建库，支持规划、子 Agent、文件系统
- **适用场景**: 需要在 LangChain 生态内构建复杂推理 Agent

### 4️⃣ MCP 生态（Model Context Protocol）⭐ 工具互操作标准
- **仓库**: [modelcontextprotocol](https://github.com/modelcontextprotocol)
- **特色**: AI Agent 工具互操作开放标准，被 Anthropic / OpenAI / Google 支持
- **适用场景**: 所有需要 Agent 连接外部工具（MCP Server）的场景

### 5️⃣ NousResearch / OpenBMB 开源模型系列
- **仓库**: [NousResearch](https://github.com/NousResearch)、[OpenBMB](https://github.com/OpenBMB)
- **特色**: 开源大模型和 Agent 训练基础设施
- **适用场景**: Agent 模型训练、研究导向的 Agent 开发

---

## 📈 五、2026年3月 AI Agent 关键趋势

| 趋势 | 描述 | 代表项目 |
|------|------|---------|
| **Agent 自进化** | Agent 从经验中学习，自我改进 | Hermes Agent |
| **Harness 性能优化** | Claude Code 等编码 Agent 的极致调优 | everything-claude-code |
| **多渠道 Agent** | 统一 Agent 支持 Telegram/Discord/飞书等 | Hermes Agent |
| **工作流引擎化** | 用 YAML/代码定义 AI 开发流程 | Archon |
| **Deep Research 爆发** | 多步研究 Agent 成为标配 | Onyx、DeepTutor |
| **Multi-Agent 协作** | 多 Agent 角色扮演、团队协作 | CrewAI、Claude-Code-Game-Studios |
| **MCP 生态统一** | 工具互操作标准加速成熟 | MCP Registry |
| **企业级框架成熟** | AutoGen → Microsoft Agent Framework | Microsoft Agent Framework |
| **TypeScript 崛起** | 前端开发者进入 Agent 开发 | Mastra、Archon |
| **垂直领域 Agent** | 金融/教育/数据等专业 Agent 涌现 | Kronos、DB-GPT、DeepTutor |

---

## 🏆 六、选品建议（按场景）

| 场景 | 推荐项目 | 理由 |
|------|---------|------|
| **个人 AI 助手** | Hermes Agent | 自改进、多渠道、低成本（$5 VPS）、开箱即用 |
| **AI 编码团队** | Archon + everything-claude-code | 标准化流程 + 性能优化组合 |
| **企业 AI 平台** | Onyx + LangGraph | Deep Research + 图形化复杂工作流 |
| **数据分析师** | DB-GPT | 自然语言 SQL + 可视化 + 沙箱安全 |
| **TypeScript 团队** | Mastra | 原生 TypeScript，React/Next.js 集成 |
| **多 Agent 协作** | CrewAI / LangGraph | 角色扮演 + 图结构工作流 |
| **快速原型** | OpenAI Agents SDK | 轻量、官方、多模型支持 |
| **金融领域** | Kronos + DB-GPT | 金融语言模型 + 数据分析 |
| **在线教育** | DeepTutor | 个性化学习，Agent 原生设计 |
| **科研轨迹收集** | Hermes Agent | 内置研究级批处理、RL 环境 |

---

## 📋 七、快速参考表

| 排名 | 项目 | Stars | 本月增长 | 分类 | 语言 | 上手指度 |
|------|------|-------|---------|------|------|---------|
| 1 | everything-claude-code | 164K | 69K ⬆️ | 框架 | JS/Python | ⭐⭐⭐ |
| 2 | hermes-agent | 110K | 100K ⬆️ | 框架/应用 | Python | ⭐⭐⭐ |
| 3 | andrej-karpathy-skills | 76K | 67K ⬆️ | 应用 | Markdown | ⭐ |
| 4 | LangGraph | 70K+ | 稳定 | 框架 | Python | ⭐⭐⭐ |
| 5 | Archon | 19K | 5.7K | 框架 | TypeScript | ⭐⭐ |
| 6 | OpenAI Agents SDK | 50K+ | 快速增长 | 框架 | Python | ⭐⭐ |
| 7 | Onyx | 28K | 10K ⬆️ | 应用 | Python | ⭐⭐ |
| 8 | DB-GPT | 20K+ | 稳定 | 应用 | Python | ⭐⭐ |
| 9 | DeepTutor | 21K | 10K ⬆️ | 研究 | Python | ⭐⭐ |
| 10 | CrewAI | 30K+ | 稳定 | 框架 | Python | ⭐⭐⭐ |

---

## 🔗 资源链接

- **Awesome Lists**: 搜索 GitHub `topic:ai-agent` 获取完整生态
- **文档**: [LangGraph Docs](https://docs.langchain.com/oss/python/langgraph), [Mastra Docs](https://mastra.ai/docs), [Hermes Docs](https://hermes-agent.nousresearch.com/docs/)
- **MCP 标准**: [modelcontextprotocol.github.io](https://modelcontextprotocol.github.io)

---

*报告生成：OpenClaw Subagent | 2026-04-23*
