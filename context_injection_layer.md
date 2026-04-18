# Context Injection Layer - 上下文注入层

> 核心问题：文件存在 ≠ 模型看到

## 问题

当前系统：
```
文件存在 → Agent自己决定用不用 → 可能忽略
```

问题：
- Agent 可能忘记读某些文件
- Agent 可能读错重点
- 没有主动注入机制

## 解决方案

```python
def build_context(user_input):
    # 1. 分析用户输入，提取关键实体
    entities = extract_entities(user_input)
    
    # 2. 匹配相关规则
    rules = match_rules(user_input)
    
    # 3. 提取相关记忆
    memory = select_memory(user_input, entities)
    
    # 4. 提取相关知识
    knowledge = select_knowledge(entities)
    
    # 5. 构建上下文
    return rules + memory + knowledge + user_input
```

## 注入时机

1. **每次用户输入时** — 自动注入
2. **每次工具调用前后** — 上下文确认
3. **每次任务开始前** — 准备上下文

## 上下文组成

```
[系统提示]
[身份定义]
[核心规则]          ← Context Injection Layer 注入
[相关记忆]          ← Context Injection Layer 注入
[相关知识]          ← Context Injection Layer 注入
[用户输入]
```

## 规则匹配

```python
def match_rules(user_input):
    matched = []
    for rule in rules:
        if rule.matches(user_input):
            matched.append(rule)
    return sorted(matched, by_confidence)
```

## 记忆选择

```python
def select_memory(user_input, entities):
    relevant = []
    for memory in all_memories:
        if memory.relevant_to(entities):
            relevant.append(memory)
    return relevant[:5]  # 最多5条
```

---

_设计: 2026-04-16_
