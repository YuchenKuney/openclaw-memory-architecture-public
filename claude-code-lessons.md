# Claude Code 源码研究 - OpenClaw借鉴计划

_基于 Claude Code 512K行源码泄露分析_
_Created: 2026-04-15_

---

## 📊 事件概要

| 项目 | 详情 |
|------|------|
| 时间 | 2026-03-31 |
| 原因 | npm包误带.source map文件 |
| 泄露量 | 512,000行TypeScript，1,884文件 |
| GitHub | 2小时50k stars（历史记录） |

---

## 🎯 可借鉴功能（按优先级）

### 第一梯队 ⭐ 立即可实现

#### 1. 三层记忆架构（已在用）
```
Layer 1: MEMORY.md (指针索引)     ← 当前：AGENTS.md + MEMORY.md
Layer 2: Topic Files (主题文件)   ← 待建：shared/brands/, shared/domain/
Layer 3: Raw Logs (原始日志)      ← 待建：memory/YYYY-MM-DD.md
```

**改进点：**
- [ ] 每行限制150字符
- [ ] 严格写纪律：只在操作成功后更新
- [ ] Trust but Verify：记忆只是提示，必须验证

#### 2. HEARTBEAT优化（Tick循环）
```
当前：固定时间触发
借鉴：<tick>消息注入 + 模型决定是否行动
```

**改进点：**
- [ ] 加入成本感知（避免空转浪费token）
- [ ] 优先级判断（重要 vs 可跳过）
- [ ] 可中断机制（用户输入优先）

#### 3. 任务状态追踪
```
借鉴：Claude Code的task文件schema
```

**改进点：**
- [ ] 统一任务状态图标
- [ ] 详细的步骤日志
- [ ] 回调处理记录

---

### 第二梯队 ⭐⭐ 需要开发

#### 4. 多Agent协作（OpenClaw已有）
```
当前：sessions_spawn基础协作
借鉴：fork/teammate/worktree三种模式
```

**改进点：**
- [ ] Agent类型定义（leader/worker/creator/researcher）
- [ ] 标准化brief模板（已部分实现）
- [ ] 跨agent上下文共享

#### 5. 工具权限分离
```
借鉴：权限与模型决策分离
```

**改进点：**
- [ ] 明确每个工具的权限级别
- [ ] 危险操作二次确认
- [ ] 敏感数据访问日志

#### 6. 记忆整合（autoDream）
```
借鉴：睡眠时自动整理记忆
```

**改进点：**
- [ ] 定期清理过期任务
- [ ] 矛盾检测（同一事件不同记录）
- [ ] 知识提炼更新

---

### 第三梯队 ⭐⭐⭐ 高级功能

#### 7. 主动提醒模式（类KAIROS）
```
借鉴：Tick循环驱动后台Agent
```

**实现前提：**
- [ ] 稳定的定时任务系统
- [ ] 优先级评估机制
- [ ] 通知渠道管理

#### 8. 上下文压缩策略
```
借鉴：5种上下文压缩策略
```

**改进点：**
- [ ] 长对话自动摘要
- [ ] 低相关信息过滤
- [ ] 关键信息提取

---

## 🚫 不借鉴的功能

| 功能 | 原因 |
|------|------|
| Undercover Mode | 违反透明原则 |
| 反蒸馏机制 | 对我们无意义 |
| Buddy电子宠物 | 与业务无关 |

---

## 📝 实现笔记

### 核心原则
1. **Trust but Verify** - 记忆只是提示，必须验证
2. **Strict Write Discipline** - 只在操作成功后更新
3. **成本感知** - 避免不必要的API调用
4. **透明** - 不隐藏身份，不欺骗用户

### 当前OpenClaw已有
- [x] Agent类型定义（leader/worker/creator/researcher/engineer）
- [x] 任务状态追踪（tasks/*.md）
- [x] 记忆系统（MEMORY.md + memory/）
- [x] HEARTBEAT机制
- [x] 团队协作（sessions_spawn/sessions_send）

### 待实现
- [ ] autoDream记忆整合 → ✅ 设计完成（shared/operations/auto-dream.md）
- [ ] 上下文压缩策略 → ✅ 设计完成（shared/operations/context-compression.md）

---

## ✅ 2026-04-15 第一批完成

- [x] shared/目录整理（brands/, domain/, operations/, errors/）
- [x] Topic Files系统（brand-registry.md, channel-map.md）
- [x] 任务模板标准化（brief-templates.md）
- [x] MEMORY.md优化（加入记忆原则）
- [x] HEARTBEAT增强（优先级+成本感知）
- [x] memory索引文件创建

---

## ✅ 2026-04-15 第二批完成

- [x] autoDream设计文档（shared/operations/auto-dream.md）
- [x] 上下文压缩策略（shared/operations/context-compression.md）

---

## 🔗 参考资料

- claw-code: https://github.com/ultraworkers/claw-code
- nano-claude-code: https://github.com/SafeRL-Lab/nano-claude-code
- 深度分析: https://codepointer.substack.com/p/claude-code-architecture-of-kairos
- 记忆架构: https://medium.com/@florisfok5/claude-codes-memory-architecture
