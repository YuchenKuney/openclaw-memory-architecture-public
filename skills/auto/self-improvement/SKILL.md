# 自我改进技能
*基于 Hermes Agent 研究，2026-04-16 创建*

## 触发条件
当满足以下任一条件时，触发自我改进：

1. **复杂任务完成** — 5+ tool calls 成功完成
2. **错误中找到解决方案** — 遇到错误后找到正确方法
3. **用户纠正** — 用户指出错误方法
4. **新工作流发现** — 发现有效的重复性任务处理方式

## 改进流程

### 1. 评估是否需要创建技能
```
问自己：
- 这个任务以后还会重复吗？
- 这个流程有可复用的模式吗？
- 用户可能再次要求吗？
```

### 2. 如果需要，创建技能文件
```markdown
# skills/auto/[任务类型]/SKILL.md

---
name: auto-task-name
description: 简短描述
version: 1.0.0
created: YYYY-MM-DD
trigger: 触发条件描述
---

## 何时使用
触发条件。

## 流程
1. 步骤一
2. 步骤二

## 注意事项
已知的坑和解决方案。
```

### 3. 记录学习
将学到的东西添加到记忆：
- 成功的方法 → 保留
- 失败的尝试 → 记录教训
- 用户偏好 → 更新 USER.md

## 容量管理

### 记忆容量检查
- 运行 `python3 /root/.openclaw/workspace/scripts/memory_check.py`
- MEMORY.md 警戒线：80% (1,760 字符)
- USER.md 警戒线：80% (1,100 字符)

### 超过容量时
1. 读取当前条目
2. 识别可合并/删除的条目
3. 合并相关条目为简短版本
4. 然后添加新条目

## 示例

### 场景：Gmail OAuth 配置
**学到的东西：**
- token 文件名转换规则要一致
- scope 要包含 gmail.compose 和 gmail.send
- refresh_token 会过期，需要处理

**创建技能：**
```markdown
# skills/auto/gmail-oauth/SKILL.md

---
name: gmail-oauth
description: Gmail OAuth 授权流程
version: 1.0.0
created: 2026-04-16
---

## 触发条件
需要为新 Gmail 账号配置 OAuth。

## 流程
1. 在 Google Cloud Console 创建凭据（桌面应用）
2. 使用 OOB 流程：`urn:ietf:wg:oauth:2.0:oob`
3. 交换 code 获取 token
4. 保存 token 到 tokens/ 目录
5. 文件名：`{email_local}_at_gmail.com.pickle`

## 注意事项
- scope 必须包含：gmail.readonly, gmail.compose, gmail.send, gmail.modify
- token 会过期，但 refresh_token 不会
- 文件名转换：只转换 @ 前面部分的 .
