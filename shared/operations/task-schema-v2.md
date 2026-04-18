# Task Schema v2.0（正式版）

## 数据结构

```yaml
task:
  id: "T-20260418-001"          # 任务唯一标识
  name: "Shopee爆款调研"        # 任务名称
  status: "running"             # pending | running | done | error
  progress: 0.3                  # 0.0-1.0，可计算
  steps:                         # 步骤数组（有序）
    - id: "S1"
      name: "趋势分析"
      status: "running"         # pending | running | done | error | waiting_for_*
      progress: 0.3              # 0.0-1.0，可计算
      eta_seconds: 120           # 预估剩余秒数，null表示未知
      type: "tool"               # tool | llm | wait | subprocess
      error: null                # 错误信息，始终存在（None表示无错误）
    - id: "S2"
      name: "报告整理"
      status: "pending"
      progress: 0.0
      eta_seconds: null
      type: "llm"
      error: null
  created_at: "2026-04-18T08:00:00+08:00"
  updated_at: "2026-04-18T08:05:00+08:00"
```

## 强制规则

1. **所有 step 必须有 status** —— 禁止使用"等待中"、"进行中"等字符串
2. **progress 必须可计算** —— `sum(s.step.progress for s in steps) / len(steps)`，禁止手写
3. **error 必须存在** —— 即使为 None 也要有字段

## Step 状态枚举

```
pending              # 未开始
running              # 进行中
waiting_for_input    # 等待用户输入
waiting_for_tool     # 等待工具返回
waiting_for_subtask  # 等待子任务完成
done                 # 完成
error                # 失败
```

## Task ↔ Memory 同步机制

### 双机制原则

```
Task（原始事件流）→ 实时写入 → Memory（压缩认知）
                     ↓
              定时蒸馏（Distiller）
```

### 实时写入（轻量事件）

```python
memory.add(
    type="task_event",
    content="T-001 S1 进行中（30%）预计120秒",
    tags=["task", "T-001", "S1"]
)
```

### 定时蒸馏（压缩认知）

```python
events = [
    "T-001 S1 进行中（30%）",
    "T-001 S1 进行中（60%）",
    "T-001 S1 完成"
]
distill(events) → "趋势分析已完成"

memory.add(
    type="task_summary",
    content="Shopee调研：趋势分析完成，进入报告整理阶段",
    tags=["task", "T-001"]
)
```

### 回写时机

- **立即写入**：每个 step 状态变化时（最大延迟 < 5秒）
- **定时蒸馏**：每小时或每 5 个事件触发一次
- **最终总结**：task 状态变为 done/error 时立即写入 summary

## 层次关系

```
唯一真相：Memory（压缩后的认知）
Task 文件：执行快照（可丢弃，不是一等公民）
注意：OpenClaw 文件系统是 IO 层，不是真相层
```
