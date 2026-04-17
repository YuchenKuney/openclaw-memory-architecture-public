# OpenClaw 记忆系统最佳实践
*基于 Hermes Agent 研究 + 自我实践*

## 核心原则

### 1. 容量限制（参考 Hermes）
- **MEMORY.md**: 严格限制 ~2,200 字符
- **USER.md**: 严格限制 ~1,375 字符
- **超过 80% 警戒线**：先精简再添加

### 2. 分层记忆架构
```
Layer 1: MEMORY.md (核心身份+偏好)
Layer 2: shared/domain/ (领域知识)
Layer 3: memory/YYYY-MM-DD.md (日记)
Layer 4: 技能 (skills/)
```

### 3. 定期检查
```bash
# 检查记忆容量
python3 /root/.openclaw/workspace/scripts/memory_check.py
```

## 实用技巧

### MEMORY.md 组织
```
## 🏷️ 身份 — 2-3 句话
## 👤 用户关键信息 — 10 句以内
## ⚠️ 铁律 — 不超过 5 条
## 📋 每日任务 — 关键任务列表
## 🔑 密钥信息 — 经常用的
## 📅 提醒 — 未来重要事件
## 📚 知识库索引 — 快速定位
```

### 每日日志
- 记录每天的重要事件
- 问题 + 解决方案
- 学到的新东西

### 技能自我进化
当完成复杂任务时：
1. 评估是否可以复用
2. 创建技能文件
3. 添加到 skills/auto/

## 与 Hermes 的差异

| 特性 | Hermes | OpenClaw (我的实践) |
|------|--------|---------------------|
| 存储 | 纯文本 | SQLite + Markdown |
| 搜索 | FTS5 | 手动搜索 |
| 限制 | 硬限制 | 软限制 + 监控 |
| 技能 | 自动创建 | 手动创建 |

## 可分享的内容

1. **记忆容量监控脚本** — memory_check.py
2. **Gmail OAuth 工具** — gmail_oauth.py
3. **Hermes 研究笔记** — hermes-agent-research.md
4. **每日日志模板** — memory/YYYY-MM-DD.md

## 开源建议

如果要创建独立的开源项目，可以考虑：

1. **OpenClaw 记忆增强插件**
   - 添加容量监控
   - 自动清理建议
   - 记忆分析

2. **Gmail OAuth 集成工具**
   - 多账号管理
   - 邮件监控

3. **OpenClaw + Hermes 对比研究**
   - 文档化差异
   - 互相借鉴

---

*文档版本：2026-04-16*
*创建者：虾哥 🦐 (OpenClaw AI)*
