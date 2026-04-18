# Brief Templates - 任务模板

_Updated: 2026-04-15_

---

## 标准任务Brief格式

```markdown
# Brief: {任务名称}
Task ID: T-{YYYYMMDD}-{HHMM}
Created: {YYYY-MM-DD HH:MM} HKT
Route: {chatId}:{threadId}
Callback to: agent:{id}:main

## 背景
{为什么需要做这个任务}

## 任务
{具体要做什么}

## 验收标准
- [ ] 标准1
- [ ] 标准2

## 执行边界
{什么可以做，什么不能做}

## 共享资源
- Brand: {brand_id}
- 品牌资料: shared/brands/{brand_id}/

## 回调要求
修改完先回報，DO NOT push/execute，等 Leader review + 確認
```

---

## 状态更新模板

```
📋 {task name}
ID: T-{id}

1. ⏳ Agent → 步骤描述
2. — Agent → 步骤描述 (after: 1)
3. — Agent → 步骤描述 (after: 2)

⏳ 進行中：Step N
```

---

## 结果交付模板

```markdown
# ✅ {任务名称} - 完成

## 执行摘要
{简要说明做了什么}

## 详细结果
{具体成果}

## 文件产出
- {path/to/file1}
- {path/to/file2}

## 下一步建议
{可选的后续行动}

---
[PENDING APPROVAL]
```

---

## Revision Request模板

```markdown
## [REVISION REQUEST] Round {N}/2

### 反馈
{具体修改意见}

### 优先级
1. 必须修改：{项目}
2. 建议修改：{项目}

### 参考
原Brief: {path}
```

---

## 状态图标

| 图标 | 含义 |
|------|------|
| ⏳ | 进行中 |
| ✅ | 完成 |
| ❌ | 失败 |
| — | 等待中（标注after:N） |
| 🔍 | 审查中 |
| ↩️ | 返工（标注N/2） |
